"""
Generation API Routes.

Endpoints for triggering and monitoring content generation.
"""
import asyncio
import inspect
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ...adapters import FpfAdapter, GptrAdapter, GenerationConfig, GeneratorType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generation", tags=["generation"])


# ============================================================================
# Request/Response Models
# ============================================================================

class GenerateRequest(BaseModel):
    """Request to generate content."""
    query: str = Field(..., min_length=1, max_length=10000, description="Research query")
    generator: GeneratorType = Field(GeneratorType.GPTR)

    # Model settings
    provider: str = Field("openai")
    model: str = Field("gpt-5")
    temperature: float = Field(0.7, ge=0, le=2)

    # GPTR-specific
    report_type: str = Field("research_report")
    report_source: str = Field("web")
    tone: str = Field("Objective")
    source_urls: list[str] = Field(default_factory=list)

    # FPF-specific
    document_content: Optional[str] = Field(None, description="Document content for FPF file_a")
    reasoning_effort: Optional[str] = Field("medium", description="FPF reasoning effort")
    max_completion_tokens: Optional[int] = Field(50000, description="FPF max completion tokens")


class GenerateResponse(BaseModel):
    """Response from generation."""
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Status of a generation task."""
    task_id: str
    status: str
    progress: float = Field(0.0, ge=0, le=1)
    stage: Optional[str] = None
    message: Optional[str] = None
    
    # Results (if completed)
    content: Optional[str] = None
    cost_usd: Optional[float] = None
    duration_seconds: Optional[float] = None
    sources: list[dict] = Field(default_factory=list)
    
    # Error (if failed)
    error: Optional[str] = None
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================================
# In-Memory Task Storage (replace with DB in production)
# ============================================================================

class TaskStore:
    """Simple in-memory task store."""
    
    def __init__(self):
        self.tasks: dict[str, dict] = {}
    
    def create(self, task_id: str, query: str, generator: str) -> dict:
        task = {
            "task_id": task_id,
            "query": query,
            "generator": generator,
            "status": "pending",
            "progress": 0.0,
            "stage": None,
            "message": None,
            "content": None,
            "cost_usd": None,
            "duration_seconds": None,
            "sources": [],
            "error": None,
            "started_at": None,
            "completed_at": None,
        }
        self.tasks[task_id] = task
        return task
    
    def get(self, task_id: str) -> Optional[dict]:
        return self.tasks.get(task_id)
    
    def update(self, task_id: str, **kwargs) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)
    
    def delete(self, task_id: str) -> None:
        self.tasks.pop(task_id, None)


task_store = TaskStore()
# Track running background tasks and their adapters for cancellation.
generation_tasks: dict[str, dict] = {}


# ============================================================================
# Background Task Runner
# ============================================================================

async def run_generation_task(
    task_id: str,
    request: GenerateRequest,
) -> None:
    """Background task to run generation."""
    
    task_store.update(task_id, status="running", started_at=datetime.utcnow())
    
    async def progress_callback(stage: str, progress: float, message: Optional[str]) -> None:
        task_store.update(
            task_id,
            stage=stage,
            progress=progress,
            message=message,
        )
        try:
            await ws_manager.broadcast(task_id, task_store.get(task_id))
        except Exception:
            pass
    
    try:
        # Get appropriate adapter
        if request.generator == GeneratorType.GPTR:
            adapter = GptrAdapter()
        elif request.generator == GeneratorType.FPF:
            adapter = FpfAdapter()
        else:
            raise ValueError(f"Unsupported generator: {request.generator}")

        # Register adapter for cancellation
        if task_id in generation_tasks:
            generation_tasks[task_id]["adapter"] = adapter
        
        # Build config with generator-specific options
        extra_config = {}
        if request.generator == GeneratorType.GPTR:
            extra_config.update({
                "report_type": request.report_type,
                "report_source": request.report_source,
                "tone": request.tone,
                "source_urls": request.source_urls,
            })
        elif request.generator == GeneratorType.FPF:
            extra_config.update({
                "task_id": task_id,
                "reasoning_effort": request.reasoning_effort,
                "max_completion_tokens": request.max_completion_tokens,
            })

        config = GenerationConfig(
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            extra=extra_config,
        )

        # Run generation
        result = await adapter.generate(
            query=request.query,
            config=config,
            document_content=request.document_content,
            progress_callback=progress_callback,
        )
        
        # Update task with results
        if result.status.value == "completed":
            task_store.update(
                task_id,
                status="completed",
                progress=1.0,
                content=result.content,
                cost_usd=result.cost_usd,
                duration_seconds=result.duration_seconds,
                sources=[s for s in result.sources],
                completed_at=datetime.utcnow(),
            )
        else:
            task_store.update(
                task_id,
                status="failed",
                error=result.error_message,
                completed_at=datetime.utcnow(),
            )
            
    except asyncio.CancelledError:
        try:
            task_store.update(
                task_id,
                status="cancelled",
                completed_at=datetime.utcnow(),
            )
            await ws_manager.broadcast(task_id, task_store.get(task_id))
        except Exception:
            pass
        raise
    except Exception as e:
        logger.exception(f"Generation task {task_id} failed")
        task_store.update(
            task_id,
            status="failed",
            error=str(e),
            completed_at=datetime.utcnow(),
        )
    finally:
        generation_tasks.pop(task_id, None)


# ============================================================================
# REST Endpoints
# ============================================================================

@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    """
    Start a new generation task.
    
    Returns immediately with a task_id. Poll /status/{task_id} for progress,
    or connect to WebSocket for real-time updates.
    """
    task_id = str(uuid4())
    
    # Create task record
    task_store.create(task_id, request.query, request.generator.value)
    
    # Start background task and track handle for cancellation
    handle = asyncio.create_task(run_generation_task(task_id, request))
    generation_tasks[task_id] = {"task": handle, "adapter": None}
    
    return GenerateResponse(
        task_id=task_id,
        status="pending",
        message="Generation task started",
    )


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Get the status of a generation task.
    """
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatusResponse(**task)


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str) -> dict:
    """
    Cancel a running generation task.
    """
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] not in ("pending", "running"):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel task in status: {task['status']}"
        )
    
    # Mark as cancelled
    task_store.update(
        task_id,
        status="cancelled",
        completed_at=datetime.utcnow(),
    )

    entry = generation_tasks.get(task_id)
    adapter = entry.get("adapter") if entry else None
    handle = entry.get("task") if entry else None

    # Best-effort adapter cancel
    if adapter:
        try:
            if inspect.iscoroutinefunction(getattr(adapter, "cancel", None)):
                await adapter.cancel(task_id)
            elif hasattr(adapter, "cancel"):
                adapter.cancel(task_id)
        except Exception:
            logger.exception(f"Adapter cancel failed for task {task_id}")

    # Cancel running task
    if handle:
        handle.cancel()
        try:
            await handle
        except asyncio.CancelledError:
            pass
    generation_tasks.pop(task_id, None)
    
    return {"status": "cancelled", "task_id": task_id}


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """
    List recent generation tasks.
    """
    tasks = list(task_store.tasks.values())
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    # Sort by started_at descending
    tasks.sort(key=lambda t: t.get("started_at") or datetime.min, reverse=True)
    
    return {
        "items": tasks[:limit],
        "total": len(tasks),
    }


# ============================================================================
# WebSocket for Real-Time Updates
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections for task updates."""
    
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}  # task_id -> connections
    
    async def connect(self, websocket: WebSocket, task_id: str) -> None:
        await websocket.accept()
        if task_id not in self.connections:
            self.connections[task_id] = []
        self.connections[task_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str) -> None:
        if task_id in self.connections:
            self.connections[task_id] = [
                ws for ws in self.connections[task_id] if ws != websocket
            ]
    
    async def broadcast(self, task_id: str, message: dict) -> None:
        if task_id in self.connections:
            for ws in self.connections[task_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


ws_manager = ConnectionManager()


@router.websocket("/ws/{task_id}")
async def websocket_task_updates(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task updates.
    
    Connect to receive progress updates for a specific task.
    """
    await ws_manager.connect(websocket, task_id)
    
    try:
        # Send initial status
        task = task_store.get(task_id)
        if task:
            await websocket.send_json(task)
        
        # Keep connection open and poll for updates
        last_status = task.copy() if task else {}
        while True:
            await asyncio.sleep(0.5)  # Poll interval
            
            task = task_store.get(task_id)
            if not task:
                await websocket.send_json({"error": "Task not found"})
                break
            
            # Send update if changed
            if task != last_status:
                await websocket.send_json(task)
                last_status = task.copy()
            
            # Close if task is done
            if task["status"] in ("completed", "failed", "cancelled"):
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, task_id)
