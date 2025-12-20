"""
Run Executor Service.

Orchestrates the full run pipeline:
1. Generation Phase - Create documents using FPF/GPTR
2. Single-Doc Evaluation - Grade each doc immediately after generation (STREAMING)
3. Pairwise Evaluation - Compare docs head-to-head (BATCH, after all single evals)
4. Combine Phase - Merge winners (optional)
5. Post-Combine Evaluation (optional)
"""

import asyncio
import logging
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..adapters.fpf.adapter import FpfAdapter
from ..adapters.gptr.adapter import GptrAdapter
from ..adapters.combine.adapter import CombineAdapter
from ..adapters.combine.config import CombineConfig
from ..adapters.base import GenerationConfig, GenerationResult, GeneratorType, ProgressCallback, TaskStatus
from ..evaluation import (
    DocumentInput,
    EvaluationConfig,
    EvaluationInput,
    EvaluationService,
    SingleDocEvaluator,
    SingleEvalConfig,
    SingleEvalSummary,
    PairwiseEvaluator,
    PairwiseConfig,
    PairwiseSummary,
    FpfStatsTracker,
)

logger = logging.getLogger(__name__)


class RunPhase(str, Enum):
    """Current phase of run execution."""
    PENDING = "pending"
    GENERATING = "generating"
    SINGLE_EVAL = "single_eval"
    PAIRWISE_EVAL = "pairwise_eval"
    COMBINING = "combining"
    POST_COMBINE_EVAL = "post_combine_eval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GeneratedDocument:
    """A document produced by generation."""
    doc_id: str
    content: str
    generator: GeneratorType
    model: str
    source_doc_id: str  # The input document ID
    iteration: int
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunConfig:
    """Configuration for a run."""
    # Inputs
    document_ids: List[str]
    document_contents: Dict[str, str]  # doc_id -> content
    
    # Generators
    generators: List[GeneratorType]
    models: List[str]  # Model names to use
    
    # Instructions/prompt for FPF (optional, has default)
    instructions: str = ""  # The prompt/instructions to use with FPF
    iterations: int = 1
    
    # Evaluation
    enable_single_eval: bool = True
    enable_pairwise: bool = True
    eval_iterations: int = 1
    eval_judge_models: List[str] = field(default_factory=list)  # REQUIRED - must be set by preset
    pairwise_top_n: Optional[int] = None  # Top-N filtering
    
    # Custom evaluation instructions (from Content Library)
    single_eval_instructions: Optional[str] = None
    pairwise_eval_instructions: Optional[str] = None
    eval_criteria: Optional[str] = None
    
    # Combine
    enable_combine: bool = False
    combine_strategy: str = ""  # REQUIRED from preset if combine enabled
    combine_models: List[str] = field(default_factory=list)  # REQUIRED - must be set by preset
    combine_instructions: Optional[str] = None  # REQUIRED from Content Library if combine enabled
    
    # Concurrency settings (from GUI Settings page) - REQUIRED from preset
    generation_concurrency: int = 5  # Max concurrent document generations
    eval_concurrency: int = 5  # Max concurrent evaluation calls  
    request_timeout: int = 600  # Request timeout in seconds - REQUIRED from GUI
    max_retries: int = 3  # Max retries on transient failures
    retry_delay: float = 2.0  # Delay between retries
    
    # Logging
    log_level: str = "INFO"  # Default INFO, can be overridden by preset
    
    # Callbacks
    on_progress: Optional[Callable[[str, float, str], None]] = None


@dataclass
class RunProgress:
    """Progress tracking for a run."""
    phase: RunPhase
    total_tasks: int
    completed_tasks: int
    current_task: Optional[str] = None
    
    @property
    def progress_percent(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


@dataclass
class RunResult:
    """Result of a completed run."""
    run_id: str
    status: RunPhase
    
    # Generated documents
    generated_docs: List[GeneratedDocument]
    
    # Evaluation results
    single_eval_results: Optional[Dict[str, SingleEvalSummary]] = None
    pairwise_results: Optional[PairwiseSummary] = None
    
    # Final output
    winner_doc_id: Optional[str] = None
    combined_content: Optional[str] = None  # Legacy: first combined doc content
    combined_doc: Optional[GeneratedDocument] = None  # Legacy: first combined doc
    combined_docs: List[GeneratedDocument] = field(default_factory=list)  # All combined docs
    
    # Post-combine evaluation
    post_combine_eval_results: Optional[PairwiseSummary] = None
    
    # Stats
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    fpf_stats: Optional[Dict[str, Any]] = None  # Live FPF call statistics
    
    # Errors
    errors: List[str] = field(default_factory=list)


class RunExecutor:
    """
    Executes a full run pipeline.
    
    Pipeline flow:
    ```
    [Input Docs] 
         │
         ▼
    ┌─────────────────────────────────────────┐
    │ GENERATION PHASE                        │
    │ For each (doc, model, iteration):       │
    │   1. Generate document                  │
    │   2. Single-eval IMMEDIATELY ◄────────┐ │  ← STREAMING
    │      (don't wait for other gens)      │ │
    └───────────────────────────────────────┘ │
                      │                       │
                      ▼ (wait for ALL)        │
    ┌─────────────────────────────────────────┐
    │ PAIRWISE PHASE (batch)                  │
    │   1. Collect all single-eval scores     │
    │   2. Filter to Top-N (optional)         │
    │   3. Run pairwise tournament            │
    │   4. Calculate Elo rankings             │
    └─────────────────────────────────────────┘
                      │
                      ▼
    [Winner Document(s)]
    ```
    """
    
    def __init__(self, ws_manager=None):
        self._fpf_adapter = FpfAdapter()
        self._gptr_adapter = GptrAdapter()
        self._cancelled = False
        self._fpf_stats = FpfStatsTracker()  # Track FPF stats across the run
        # NOTE: Callback is set in execute() with run_id closure, not here
        
        # Use injected WebSocket manager or try to import if not provided (legacy fallback)
        if ws_manager:
            self._run_ws_manager = ws_manager
        else:
            try:
                from ..api.websockets import run_ws_manager
                self._run_ws_manager = run_ws_manager
            except Exception:
                self._run_ws_manager = None
            
        # Debug: surface executor creation info
        try:
            logger.debug(
                "RunExecutor.__init__ created fpf_adapter=%r gptr_adapter=%r cancelled=%s ws_manager=%s",
                type(self._fpf_adapter).__name__,
                type(self._gptr_adapter).__name__,
                self._cancelled,
                "INJECTED" if ws_manager else ("IMPORTED" if self._run_ws_manager else "NONE")
            )
        except Exception:
            logger.debug("RunExecutor.__init__ debug log failed", exc_info=True)
            
    def _broadcast_stats(self, stats: FpfStatsTracker, run_id: str):
        """Broadcast updated FPF stats via WebSocket.
        
        Args:
            stats: The stats tracker with current counts
            run_id: The run ID to broadcast to (captured in closure at execute() start)
        """
        # CRITICAL DEBUG: This should appear in logs!
        logger.info(f"[STATS] _broadcast_stats ENTERED! run_id={run_id}")
        
        # Fix #8: Validate run_id matches current active run
        current_run = getattr(self, '_current_run_id', None)
        if current_run and current_run != run_id:
            logger.warning(f"[STATS] RUN ID MISMATCH! Broadcast target={run_id}, but current executor run={current_run}. Skipping stale broadcast.")
            return
            
        logger.info(f"[STATS] Checking ws_manager: {self._run_ws_manager is not None}")
        if not self._run_ws_manager:
            logger.warning(f"[STATS] Cannot broadcast for run {run_id}: WebSocket manager not initialized")
            return
        
        try:
            # Serialize stats with validation
            stats_dict = stats.to_dict()
            logger.info(f"[STATS] Broadcasting stats for run {run_id}: {stats_dict}")
            
            # Create stats payload
            payload = {
                "event": "fpf_stats_update",
                "stats": stats_dict
            }
            
            # Try to broadcast via event loop
            try:
                loop = asyncio.get_running_loop()
                logger.info(f"[STATS] Got running loop, creating task")
                task = loop.create_task(self._run_ws_manager.broadcast(run_id, payload))
                logger.info(f"[STATS] WebSocket broadcast task created for run {run_id}")
            except RuntimeError as e:
                logger.warning(f"[STATS] No running event loop for run {run_id}: {e}")
        except Exception as e:
            logger.error(f"[STATS] Failed to broadcast stats for run {run_id}: {e}", exc_info=True)
    
    async def _emit_timeline_event(
        self,
        run_id: str,
        phase: str,
        event_type: str,
        description: str,
        model: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_seconds: Optional[float] = None,
        success: bool = True,
        details: Optional[dict] = None,
    ) -> None:
        """Emit a timeline event to the database for progressive UI updates.
        
        This appends an event to results_summary.timeline_events so the frontend
        can show timeline progress during execution, not just at completion.
        """
        from ..infra.db.session import async_session_factory
        from ..infra.db.repositories import RunRepository
        
        event = {
            "phase": phase,
            "event_type": event_type,
            "description": description,
            "model": model,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "duration_seconds": duration_seconds,
            "success": success,
            "details": details,
        }
        
        try:
            async with async_session_factory() as session:
                run_repo = RunRepository(session)
                await run_repo.append_timeline_event(run_id, event)
                logger.debug(f"Emitted timeline event: {phase}/{event_type} for run {run_id}")
        except Exception as e:
            logger.warning(f"Failed to emit timeline event for run {run_id}: {e}")
    
    def _get_adapter(self, generator: GeneratorType):
        """Get adapter for generator type."""
        if generator == GeneratorType.FPF:
            return self._fpf_adapter
        elif generator == GeneratorType.GPTR:
            return self._gptr_adapter
        else:
            raise ValueError(f"Unknown generator: {generator}")
    
    async def _save_generated_content(self, run_id: str, gen_doc: GeneratedDocument) -> None:
        """Save generated document content to a file for later retrieval.
        
        Files are stored in logs/{run_id}/generated/{doc_id}.md
        """
        from pathlib import Path
        import aiofiles
        
        try:
            # Create directory structure
            gen_dir = Path("logs") / run_id / "generated"
            gen_dir.mkdir(parents=True, exist_ok=True)
            
            # Sanitize doc_id for filename (replace invalid chars)
            safe_doc_id = gen_doc.doc_id.replace(':', '_').replace('/', '_').replace('\\', '_')
            file_path = gen_dir / f"{safe_doc_id}.md"
            
            # Write content
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(gen_doc.content or "")
            
            logger.debug(f"Saved generated content to {file_path}")
        except Exception as e:
            logger.exception(f"Failed to save generated content for {gen_doc.doc_id}: {e}")
    
    async def execute(self, run_id: str, config: RunConfig) -> RunResult:
        """
        Execute a full run.
        
        Args:
            run_id: Unique run identifier
            config: Run configuration
            
        Returns:
            RunResult with all outputs and stats
        """
        # CRITICAL: Set run_id FIRST before any other operations
        self._current_run_id = run_id
        logger.info(f"[STATS] Initializing executor for run {run_id}")
        
        # Fix #5: Reset stats for new run
        # Fix #3: Create closure that captures run_id to prevent stale ID issues
        self._fpf_stats = FpfStatsTracker()
        captured_run_id = run_id  # Capture in local variable for closure
        self._fpf_stats._on_update = lambda stats: self._broadcast_stats(stats, captured_run_id)
        logger.info(f"[STATS] FpfStatsTracker initialized with broadcast callback bound to run_id={captured_run_id}")
        
        started_at = datetime.utcnow()
        result = RunResult(
            run_id=run_id,
            status=RunPhase.GENERATING,
            generated_docs=[],
            started_at=started_at,
        )
        
        # Debug: log a concise run config summary (no secrets)
        try:
            logger.debug(
                "Run %s config summary: documents=%d models=%r generators=%r iterations=%d enable_single_eval=%s enable_pairwise=%s log_level=%s",
                run_id,
                len(config.document_ids or []),
                config.models,
                [g.value for g in (config.generators or [])],
                config.iterations,
                config.enable_single_eval,
                config.enable_pairwise,
                config.log_level,
            )
        except Exception:
            logger.debug("Failed to log run config summary", exc_info=True)

        # Emit run start timeline event
        await self._emit_timeline_event(
            run_id=run_id,
            phase="initialization",
            event_type="start",
            description="Run started",
            timestamp=started_at,
            success=True,
        )
        
        try:
            # Phase 1: Generation + Streaming Single Eval
            logger.info(f"Run {run_id}: Starting generation phase")
            await self._run_generation_with_eval(run_id, config, result)
            
            if self._cancelled:
                result.status = RunPhase.CANCELLED
                # Ensure stats are included even if cancelled
                try:
                    result.fpf_stats = self._fpf_stats.to_dict()
                except Exception:
                    pass
                return result
            
            # Phase 2: Pairwise Evaluation (batch, after all single evals)
            if config.enable_pairwise and len(result.generated_docs) >= 2:
                logger.info(f"Run {run_id}: Starting pairwise phase")
                result.status = RunPhase.PAIRWISE_EVAL
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_pairwise(config, result)
            
            if self._cancelled:
                result.status = RunPhase.CANCELLED
                # Ensure stats are included even if cancelled
                try:
                    result.fpf_stats = self._fpf_stats.to_dict()
                except Exception:
                    pass
                return result
            
            # If pairwise was disabled but we have single eval results, determine winner from scores
            if not result.winner_doc_id and result.single_eval_results and config.enable_combine:
                # Find doc with highest average score from single eval
                doc_scores = {}
                for doc_id, summary in result.single_eval_results.items():
                    if hasattr(summary, 'weighted_avg_score') and summary.weighted_avg_score is not None:
                        doc_scores[doc_id] = summary.weighted_avg_score
                    elif hasattr(summary, 'avg_score') and summary.avg_score is not None:
                        doc_scores[doc_id] = summary.avg_score
                
                if doc_scores:
                    result.winner_doc_id = max(doc_scores, key=doc_scores.get)
                    logger.info(f"Run {run_id}: Winner determined from single eval scores: {result.winner_doc_id} (score: {doc_scores[result.winner_doc_id]:.2f})")
                    if getattr(self, '_run_store', None):
                        try:
                            self._run_store.update(run_id, winner_doc_id=result.winner_doc_id)
                        except Exception:
                            pass
            
            # Phase 3: Combine (optional)
            if config.enable_combine and result.winner_doc_id:
                logger.info(f"Run {run_id}: Starting combine phase")
                result.status = RunPhase.COMBINING
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_combine(config, result)
            
            # Phase 4: Post-Combine Eval (optional)
            if config.enable_combine and result.combined_doc and (config.enable_single_eval or config.enable_pairwise):
                logger.info(f"Run {run_id}: Starting post-combine eval phase")
                result.status = RunPhase.POST_COMBINE_EVAL
                if getattr(self, '_run_store', None):
                    try:
                        self._run_store.update(run_id, current_phase=result.status.value)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "phase", "phase": result.status.value, "run": self._run_store.get(run_id)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                await self._run_post_combine_eval(config, result)

            # Done
            result.status = RunPhase.COMPLETED
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            
            # Include FPF stats in result
            try:
                result.fpf_stats = self._fpf_stats.to_dict()
                logger.info(f"[STATS] Stored final stats in result for run {run_id}: {result.fpf_stats}")
            except Exception as e:
                logger.error(f"[STATS] Failed to serialize stats for run {run_id}: {e}", exc_info=True)
                result.fpf_stats = None
            
            # Emit run completion timeline event
            await self._emit_timeline_event(
                run_id=run_id,
                phase="completion",
                event_type="complete",
                description="Run completed successfully",
                timestamp=result.completed_at,
                duration_seconds=result.duration_seconds,
                success=True,
            )
            
            logger.info(
                f"Run {run_id}: Completed | "
                f"docs={len(result.generated_docs)} "
                f"winner={result.winner_doc_id} "
                f"cost=${result.total_cost_usd:.4f}"
            )
            
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Run {run_id} failed: {e}\n{tb}")
            result.status = RunPhase.FAILED
            # Store both message and full traceback for diagnostics
            result.errors.append(str(e))
            result.errors.append(tb)
            result.completed_at = datetime.utcnow()
            
            # Include FPF stats even on failure
            try:
                result.fpf_stats = self._fpf_stats.to_dict()
                logger.info(f"[STATS] Stored stats from failed run {run_id}: {result.fpf_stats}")
            except Exception as stats_err:
                logger.error(f"[STATS] Failed to serialize stats for failed run {run_id}: {stats_err}", exc_info=True)
                result.fpf_stats = None
            
            # Emit run failure timeline event
            await self._emit_timeline_event(
                run_id=run_id,
                phase="completion",
                event_type="failed",
                description=f"Run failed: {str(e)[:100]}",
                timestamp=result.completed_at,
                success=False,
                details={"error": str(e)},
            )
        
        return result
    
    async def _run_generation_with_eval(
        self,
        run_id: str,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run generation phase with streaming single-doc evaluation.
        
        Each document is evaluated IMMEDIATELY after generation,
        not waiting for other documents to complete.
        """
        # Build task list: (doc_id, generator, model, iteration)
        tasks = []
        for doc_id in config.document_ids:
            for generator in config.generators:
                for model in config.models:
                    for iteration in range(1, config.iterations + 1):
                        tasks.append((doc_id, generator, model, iteration))

        # Initialize run_store tasks list so WebSocket clients see initial progress
        if getattr(self, '_run_store', None):
            try:
                initial_tasks = []
                for doc_id, generator, model, iteration in tasks:
                    # gen_doc_id same format used elsewhere
                    task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
                    initial_tasks.append({
                        "id": task_id,
                        "document_id": doc_id,
                        "document_name": doc_id,
                        "generator": generator.value,
                        "model": model,
                        "iteration": iteration,
                        "status": "pending",
                            "progress": 0.0,
                            "message": None,
                        "score": None,
                        "cost_usd": 0.0,
                        "duration_seconds": 0.0,
                        "started_at": None,
                        "completed_at": None,
                        "error_message": None,
                    })
                self._run_store.update(run_id, tasks=initial_tasks)
                if getattr(self, '_run_ws_manager', None):
                    try:
                        await self._run_ws_manager.broadcast(run_id, {"event": "init", "tasks": initial_tasks})
                    except Exception:
                        pass
            except Exception:
                pass
        
        total_tasks = len(tasks)
        completed = 0
        
        # Setup single-doc evaluator if enabled
        single_evaluator = None
        if config.enable_single_eval:
            # VALIDATE: single_eval_instructions MUST be provided from Content Library
            if not config.single_eval_instructions:
                raise RuntimeError(
                    "Single evaluation is enabled but no single_eval_instructions provided. "
                    "You must configure single_eval_instructions_id in your preset to point to "
                    "a Content Library item containing the evaluation prompt."
                )
            # VALIDATE: eval_judge_models MUST be provided from preset
            if not config.eval_judge_models:
                raise RuntimeError(
                    "Single evaluation is enabled but no judge models configured. "
                    "You must configure eval_config.judge_models in your preset's config_overrides."
                )
            eval_config = SingleEvalConfig(
                iterations=config.eval_iterations,
                judge_models=config.eval_judge_models,
                custom_instructions=config.single_eval_instructions,
                custom_criteria=config.eval_criteria,
                concurrent_limit=config.eval_concurrency,
            )
            logger.info(f"[STATS-DEBUG] Creating SingleDocEvaluator with stats_tracker={self._fpf_stats is not None}")
            single_evaluator = SingleDocEvaluator(eval_config, stats_tracker=self._fpf_stats)
            result.single_eval_results = {}
        
        # Process tasks with limited concurrency (from settings)
        semaphore = asyncio.Semaphore(config.generation_concurrency)
        
        async def process_task(task_info):
            nonlocal completed
            doc_id, generator, model, iteration = task_info
            
            async with semaphore:
                if self._cancelled:
                    return
                
                nonlocal result
                # Update run_store to set task to running
                task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
                if getattr(self, '_run_store', None):
                    run = self._run_store.get(run_id)
                    if run:
                        tasks_list = run.get('tasks', [])
                        for t in tasks_list:
                            if t['id'] == task_id:
                                t['status'] = 'running'
                                t['progress'] = 0.05
                                t['message'] = 'started'
                                t['started_at'] = datetime.utcnow()
                                break
                        self._run_store.update(run_id, tasks=tasks_list)
                        if getattr(self, '_run_ws_manager', None):
                            try:
                                await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": t})
                            except Exception:
                                pass

                # Progress callback for this specific task
                async def _progress_callback(stage: str, progress: float, message: Optional[str]):
                    # Update the run_store task entry
                    if getattr(self, '_run_store', None):
                        run = self._run_store.get(run_id)
                        if run:
                            tasks_list = run.get('tasks', [])
                            for tt in tasks_list:
                                if tt['id'] == task_id:
                                    tt['progress'] = progress
                                    tt['message'] = message
                                    break
                            self._run_store.update(run_id, tasks=tasks_list)
                            # Broadcast to run-level WS
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": tt})
                                except Exception:
                                    pass
                    # Also broadcast to task-level WS manager if available
                    try:
                        from ..api.routes.generation import ws_manager as gen_ws_manager
                        await gen_ws_manager.broadcast(task_id, {"event": "progress", "task_id": task_id, "stage": stage, "progress": progress, "message": message})
                    except Exception:
                        pass

                # 1. Generate
                gen_result = await self._generate_single(
                    doc_id=doc_id,
                    content=config.document_contents[doc_id],
                    instructions=config.instructions,
                    generator=generator,
                    model=model,
                    iteration=iteration,
                    progress_callback=_progress_callback,
                    log_level=config.log_level,
                    run_id=run_id,
                    timeout=config.request_timeout,
                )
                
                if gen_result:
                    result.generated_docs.append(gen_result)
                    result.total_cost_usd += gen_result.cost_usd
                    
                    # Save generated content to file for later retrieval
                    await self._save_generated_content(run_id, gen_result)
                    
                    # Emit generation timeline event
                    gen_completed_at = gen_result.completed_at if hasattr(gen_result, 'completed_at') and gen_result.completed_at else datetime.utcnow()
                    await self._emit_timeline_event(
                        run_id=run_id,
                        phase="generation",
                        event_type="generation",
                        description=f"Generated doc using {generator.value}",
                        model=model,
                        timestamp=gen_result.started_at if hasattr(gen_result, 'started_at') and gen_result.started_at else None,
                        completed_at=gen_completed_at,
                        duration_seconds=gen_result.duration_seconds,
                        success=True,
                        details={"doc_id": gen_result.doc_id},
                    )
                    
                    # 2. Single eval IMMEDIATELY (streaming)
                    if single_evaluator and gen_result.content:
                        try:
                            eval_input = DocumentInput(
                                doc_id=gen_result.doc_id,
                                content=gen_result.content,
                            )
                            eval_started_at = datetime.utcnow()
                            summary = await single_evaluator.evaluate_document(eval_input)
                            result.single_eval_results[gen_result.doc_id] = summary
                            eval_completed_at = datetime.utcnow()
                            
                            # Emit single eval timeline event
                            await self._emit_timeline_event(
                                run_id=run_id,
                                phase="evaluation",
                                event_type="single_eval",
                                description=f"Evaluated {gen_result.doc_id[:20]}...",
                                model=", ".join(config.eval_judge_models) if config.eval_judge_models else None,
                                timestamp=eval_started_at,
                                completed_at=eval_completed_at,
                                duration_seconds=(eval_completed_at - eval_started_at).total_seconds(),
                                success=True,
                                details={
                                    "doc_id": gen_result.doc_id,
                                    "average_score": summary.avg_score,
                                },
                            )
                            
                            # Broadcast eval score via WebSocket for live UI updates
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {
                                        "event": "eval_complete",
                                        "doc_id": gen_result.doc_id,
                                        "average_score": summary.avg_score,
                                        "scores_by_model": {m: s.avg_score for m, s in summary.model_scores.items()} if hasattr(summary, 'model_scores') and summary.model_scores else {},
                                        "duration_seconds": (eval_completed_at - eval_started_at).total_seconds(),
                                    })
                                except Exception:
                                    pass
                            
                            logger.info(
                                f"Single eval complete: {gen_result.doc_id} | "
                                f"avg={summary.avg_score:.2f}"
                            )
                        except Exception as e:
                            logger.error(f"Single eval failed for {gen_result.doc_id}: {e}")
                            result.errors.append(f"Single eval failed: {gen_result.doc_id}")
                    # Update run_store: mark task completed
                    if getattr(self, '_run_store', None):
                        run = self._run_store.get(run_id)
                        if run:
                            tasks_list = run.get('tasks', [])
                            for t in tasks_list:
                                if t['id'] == task_id:
                                    t['status'] = 'completed'
                                    t['progress'] = 1.0
                                    t['message'] = 'completed'
                                    t['cost_usd'] = gen_result.cost_usd or 0.0
                                    t['duration_seconds'] = gen_result.duration_seconds or 0.0
                                    t['completed_at'] = datetime.utcnow()
                                    break
                            self._run_store.update(run_id, tasks=tasks_list, total_cost_usd=result.total_cost_usd)
                            if getattr(self, '_run_ws_manager', None):
                                try:
                                    await self._run_ws_manager.broadcast(run_id, {"event": "task_update", "task": t})
                                except Exception:
                                    pass
                
                completed += 1
                if config.on_progress:
                    config.on_progress(
                        "generating",
                        completed / total_tasks,
                        f"Generated {completed}/{total_tasks}",
                    )
        
        # Run all tasks
        await asyncio.gather(*[process_task(t) for t in tasks])

    async def _generate_single(
        self,
        doc_id: str,
        content: str,
        instructions: str,
        generator: GeneratorType,
        model: str,
        iteration: int,
        progress_callback: Optional[ProgressCallback] = None,
        log_level: str = "INFO",
        run_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Optional[GeneratedDocument]:
        """Generate a single document."""
        started_at = datetime.utcnow()
        
        # Track generation start in live stats
        if self._fpf_stats:
            self._fpf_stats.record_call_start("generation", f"Generating {doc_id} with {model}")
        
        try:
            adapter = self._get_adapter(generator)
            
            # Pass model string as-is to adapter - FPF handles model/provider logic
            # Model can be "gpt-5", "openai:gpt-5", etc. Adapter decides how to use it.
            gen_config = GenerationConfig(
                provider="openai",  # Default, adapter may override based on model
                model=model,
            )
            
            # pass run-specific task id to adapter via config.extra
            task_id = f"{doc_id}.{generator.value}.{iteration}.{model}"
            if not gen_config.extra:
                gen_config.extra = {}
            gen_config.extra["task_id"] = task_id
            if timeout:
                gen_config.extra["timeout"] = timeout

            # For FPF: query=instructions, document_content=the document
            # For GPTR: query=the document content (GPTR generates research, not processes docs)
            if generator == GeneratorType.FPF:
                # Compute FPF log settings based on log_level
                fpf_log_output = "console"
                fpf_log_file = None
                run_log_file = None
                if run_id:
                    from pathlib import Path
                    log_dir = Path("logs") / run_id
                    log_dir.mkdir(parents=True, exist_ok=True)
                    # Always stream FPF output to the run log file
                    run_log_file = str(log_dir / "run.log")
                    if log_level == "VERBOSE":
                        fpf_log_output = "file"
                        fpf_log_file = str(log_dir / "fpf_output.log")
                elif log_level in ("ERROR", "WARNING"):
                    fpf_log_output = "none"
                
                gen_result = await adapter.generate(
                    query=instructions or "",  # Instructions come from preset, no fallback
                    config=gen_config,
                    document_content=content,
                    progress_callback=progress_callback,
                    fpf_log_output=fpf_log_output,
                    fpf_log_file=fpf_log_file,
                    run_log_file=run_log_file,
                )
            else:
                # GPTR and others use query as the research topic
                gen_result = await adapter.generate(
                    query=content,
                    config=gen_config,
                    progress_callback=progress_callback,
                )
            
            completed_at = datetime.utcnow()
            # Create unique doc ID for this generation
            # Use last 8 chars of source doc UUID + 4-char random ID for shorter filenames
            short_doc_id = doc_id[-8:] if len(doc_id) >= 8 else doc_id
            file_uuid = str(uuid4())[:4]
            gen_doc_id = f"{short_doc_id}.{file_uuid}.{generator.value}.{iteration}.{model.replace(':', '_')}"
            
            # Track generation success
            if self._fpf_stats:
                self._fpf_stats.record_success()
            
            return GeneratedDocument(
                doc_id=gen_doc_id,
                content=gen_result.content,
                generator=generator,
                model=model,
                source_doc_id=doc_id,
                iteration=iteration,
                cost_usd=gen_result.cost_usd or 0.0,
                duration_seconds=gen_result.duration_seconds or (completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
            )
            
        except Exception as e:
            logger.exception(f"Generation failed: {doc_id} {generator} {model}: {e}")
            # Track generation failure
            if self._fpf_stats:
                self._fpf_stats.record_failure(str(e))
            return None
    
    async def _run_pairwise(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run pairwise evaluation phase.
        
        This runs AFTER all single-doc evaluations are complete.
        Uses single-eval scores for optional top-N filtering.
        """
        # VALIDATE: pairwise_eval_instructions MUST be provided from Content Library
        if not config.pairwise_eval_instructions:
            raise RuntimeError(
                "Pairwise evaluation is enabled but no pairwise_eval_instructions provided. "
                "You must configure pairwise_eval_instructions_id in your preset to point to "
                "a Content Library item containing the pairwise comparison prompt."
            )
        # VALIDATE: eval_judge_models MUST be provided from preset
        if not config.eval_judge_models:
            raise RuntimeError(
                "Pairwise evaluation is enabled but no judge models configured. "
                "You must configure eval_config.judge_models in your preset's config_overrides."
            )
        
        pairwise_config = PairwiseConfig(
            iterations=config.eval_iterations,
            judge_models=config.eval_judge_models,
            top_n=config.pairwise_top_n,
            custom_instructions=config.pairwise_eval_instructions,
            concurrent_limit=config.eval_concurrency,
        )
        evaluator = PairwiseEvaluator(pairwise_config, stats_tracker=self._fpf_stats)
        
        # Collect doc IDs and contents, filtering out empty content
        # Note: All docs in generated_docs are successful (failed generations return None and aren't added)
        valid_docs = [
            doc for doc in result.generated_docs
            if doc.content and len(doc.content.strip()) > 0
        ]
        if len(valid_docs) < len(result.generated_docs):
            failed_count = len(result.generated_docs) - len(valid_docs)
            logger.warning(f"Excluding {failed_count} failed/empty documents from pairwise evaluation")
        
        doc_ids = [doc.doc_id for doc in valid_docs]
        contents = {doc.doc_id: doc.content for doc in valid_docs}
        
        # Get single-eval scores for top-N filtering
        scores = None
        if result.single_eval_results and config.pairwise_top_n:
            scores = {
                doc_id: summary.weighted_avg_score
                for doc_id, summary in result.single_eval_results.items()
            }
            doc_ids = evaluator.filter_top_n(doc_ids, scores, config.pairwise_top_n)

        contents = {d: contents[d] for d in doc_ids}
        logger.info(f"Filtered to top {len(doc_ids)} docs for pairwise")

        # Run pairwise
        pairwise_started_at = datetime.utcnow()
        summary = await evaluator.evaluate_all_pairs(doc_ids, contents)
        pairwise_completed_at = datetime.utcnow()
        result.pairwise_results = summary
        result.winner_doc_id = summary.winner_doc_id
        
        # Emit pairwise timeline event
        await self._emit_timeline_event(
            run_id=result.run_id,
            phase="pairwise",
            event_type="pairwise_eval",
            description=f"Pairwise evaluation: {summary.total_comparisons} comparisons",
            model=", ".join(config.eval_judge_models) if config.eval_judge_models else None,
            timestamp=pairwise_started_at,
            completed_at=pairwise_completed_at,
            duration_seconds=(pairwise_completed_at - pairwise_started_at).total_seconds(),
            success=True,
            details={
                "total_comparisons": summary.total_comparisons,
                "winner_doc_id": summary.winner_doc_id,
            },
        )
        
        logger.info(
            f"Pairwise complete | "
            f"comparisons={summary.total_comparisons} "
            f"winner={summary.winner_doc_id}"
        )
        # Update run store with pairwise results
        if getattr(self, '_run_store', None):
            try:
                self._run_store.update(result.run_id, total_cost_usd=result.total_cost_usd, winner_doc_id=result.winner_doc_id)
                if getattr(self, '_run_ws_manager', None):
                    try:
                        await self._run_ws_manager.broadcast(result.run_id, {"event": "pairwise", "winner": result.winner_doc_id, "run": self._run_store.get(result.run_id)})
                    except Exception:
                        pass
            except Exception:
                pass
    
    async def _run_combine(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """Run combine phase with multiple combine models."""
        if not result.winner_doc_id:
            logger.warning("Combine skipped: No winner document found")
            return
        
        # VALIDATE: combine_models MUST be provided from preset
        if not config.combine_models:
            raise RuntimeError(
                "Combine is enabled but no combine models configured. "
                "You must configure combine_config.selected_models in your preset's config_overrides."
            )

        try:
            # Use FPF for combination by default
            combine_adapter = CombineAdapter(self._fpf_adapter)
            
            # Get top docs from pairwise results
            top_docs = []
            top_ids = []
            if result.pairwise_results and result.pairwise_results.rankings:
                # rankings returns List[Tuple[str, float]] as (doc_id, rating)
                top_ids = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
                top_docs = [
                    doc.content 
                    for doc in result.generated_docs 
                    if doc.doc_id in top_ids
                ]
            
            if len(top_docs) < 2:
                logger.warning("Combine skipped: Need at least 2 top documents")
                return

            # Combine instructions - REQUIRED from Content Library via preset
            combine_instructions = config.combine_instructions
            if not combine_instructions:
                raise ValueError(
                    "Combine is enabled but no combine_instructions provided. "
                    "You must configure combine_instructions_id in your preset to point to "
                    "a Content Library item with combine instructions."
                )
            
            # Get original instructions for context
            original_instructions = ""
            if result.generated_docs:
                original_instructions = config.document_contents.get(result.generated_docs[0].source_doc_id, "")
            
            # Iterate over all combine models
            for idx, combine_model in enumerate(config.combine_models):
                try:
                    # Parse provider:model format
                    if ":" in combine_model:
                        provider, model_name = combine_model.split(":", 1)
                    else:
                        provider = "openai"
                        model_name = combine_model
                    
                    combine_gen_config = GenerationConfig(
                        provider=provider,
                        model=model_name,
                    )
                    
                    combine_started_at = datetime.utcnow()
                    logger.info(f"Combining with model {combine_model} ({idx + 1}/{len(config.combine_models)})")
                    
                    combine_result = await combine_adapter.combine(
                        reports=top_docs,
                        instructions=combine_instructions,
                        config=combine_gen_config,
                        original_instructions=original_instructions
                    )
                    combine_completed_at = datetime.utcnow()
                    combine_duration = (combine_completed_at - combine_started_at).total_seconds()
                    
                    result.total_cost_usd += combine_result.cost_usd
                    
                    # Create unique doc_id with model info
                    # Use last 8 chars of run_id + 4-char random ID for shorter filenames
                    safe_model_name = combine_model.replace(":", "_")
                    short_run_id = result.run_id[-8:] if len(result.run_id) >= 8 else result.run_id
                    file_uuid = str(uuid4())[:4]
                    combined_doc_id = f"combined.{short_run_id}.{file_uuid}.{safe_model_name}"
                    
                    # Create GeneratedDocument for combined content
                    combined_doc = GeneratedDocument(
                        doc_id=combined_doc_id,
                        content=combine_result.content,
                        generator=GeneratorType.FPF,
                        model=combine_model,
                        source_doc_id=result.generated_docs[0].source_doc_id if result.generated_docs else "",
                        iteration=1,
                        cost_usd=combine_result.cost_usd,
                        duration_seconds=combine_duration,
                        started_at=combine_started_at,
                        completed_at=combine_completed_at,
                    )
                    
                    # Add to list of combined docs
                    result.combined_docs.append(combined_doc)
                    
                    # Save combined content to file for later retrieval
                    await self._save_generated_content(result.run_id, combined_doc)
                    
                    # Set legacy fields to first combined doc for backwards compat
                    if idx == 0:
                        result.combined_content = combine_result.content
                        result.combined_doc = combined_doc
                    
                    # Emit combine timeline event for this model
                    await self._emit_timeline_event(
                        run_id=result.run_id,
                        phase="combination",
                        event_type="combine",
                        description=f"Combined documents using {combine_model}",
                        model=combine_model,
                        timestamp=combine_started_at,
                        completed_at=combine_completed_at,
                        duration_seconds=combine_duration,
                        success=True,
                        details={"combined_doc_id": combined_doc_id},
                    )
                    
                    logger.info(f"Combine with {combine_model} complete. Cost: ${combine_result.cost_usd:.4f}")
                    
                except Exception as e:
                    logger.error(f"Combine with {combine_model} failed: {e}")
                    result.errors.append(f"Combine with {combine_model} failed: {str(e)}")
            
            # Broadcast update after all combines
            if getattr(self, '_run_store', None):
                try:
                    self._run_store.update(result.run_id, total_cost_usd=result.total_cost_usd)
                    if getattr(self, '_run_ws_manager', None):
                        try:
                            await self._run_ws_manager.broadcast(result.run_id, {"event": "combine", "run": self._run_store.get(result.run_id)})
                        except Exception:
                            pass
                except Exception:
                    pass
            
            logger.info(f"All combines complete. Total combined docs: {len(result.combined_docs)}")
            
        except Exception as e:
            logger.error(f"Combine failed: {e}")
            result.errors.append(f"Combine failed: {str(e)}")

    async def _run_post_combine_eval(
        self,
        config: RunConfig,
        result: RunResult,
    ) -> None:
        """
        Run pairwise evaluation including all generated docs and all combined docs.
        
        This compares ALL documents:
        - All original generated documents
        - All combined documents
        """
        if not result.combined_docs:
            logger.warning("Post-combine eval skipped: No combined documents")
            return

        try:
            if config.enable_pairwise:
                pairwise_config = PairwiseConfig(
                    iterations=config.eval_iterations,
                    judge_models=config.eval_judge_models,
                    top_n=None,
                    custom_instructions=config.pairwise_eval_instructions,
                    concurrent_limit=config.eval_concurrency,
                )
                evaluator = PairwiseEvaluator(pairwise_config, stats_tracker=self._fpf_stats)
                
                # Build list of documents: only those sent to combiner + all combined
                all_doc_ids = []
                all_contents = {}
                
                # Get the doc IDs that were sent to combiner (top N from pairwise rankings)
                docs_sent_to_combiner = []
                if result.pairwise_results and result.pairwise_results.rankings:
                    # rankings is List[Tuple[str, float]] as (doc_id, rating) - get top 2
                    docs_sent_to_combiner = [doc_id for doc_id, rating in result.pairwise_results.rankings[:2]]
                
                # Add only the docs that were sent to combiner
                for doc in result.generated_docs:
                    if doc.doc_id in docs_sent_to_combiner:
                        all_doc_ids.append(doc.doc_id)
                        all_contents[doc.doc_id] = doc.content
                
                # Add all combined docs
                for combined_doc in result.combined_docs:
                    all_doc_ids.append(combined_doc.doc_id)
                    all_contents[combined_doc.doc_id] = combined_doc.content
                
                if len(all_doc_ids) < 2:
                    logger.warning("Post-combine eval skipped: Need at least 2 documents")
                    return
                
                logger.info(f"Post-combine pairwise: comparing {len(all_doc_ids)} documents ({len(docs_sent_to_combiner)} sent to combiner + {len(result.combined_docs)} combined)")
                
                summary = await evaluator.evaluate_all_pairs(all_doc_ids, all_contents)
                result.post_combine_eval_results = summary
                
                logger.info(
                    f"Post-combine pairwise complete | "
                    f"winner={summary.winner_doc_id} | "
                    f"total_comparisons={summary.total_comparisons}"
                )
                
                if getattr(self, '_run_store', None):
                    try:
                        if getattr(self, '_run_ws_manager', None):
                            await self._run_ws_manager.broadcast(result.run_id, {
                                "event": "post_combine_eval", 
                                "winner": summary.winner_doc_id,
                                "summary": asdict(summary) if hasattr(summary, 'to_dict') else summary.__dict__
                            })
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Post-combine eval failed: {e}")
            result.errors.append(f"Post-combine eval failed: {str(e)}")
    
    def cancel(self) -> None:
        """Cancel the running execution."""
        self._cancelled = True


# Note: RunExecutor instances are created per-run by callers to ensure
# cancellation and internal state do not leak between runs.


def get_executor() -> RunExecutor:
    """Compatibility shim: return a fresh RunExecutor instance.

    Old code imported `get_executor()` expecting a singleton; we return
    a new instance to preserve per-run isolation while keeping imports
    working for older modules.
    """
    logger.debug("get_executor() called - returning new RunExecutor instance")
    return RunExecutor()
