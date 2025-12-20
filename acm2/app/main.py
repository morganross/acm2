"""
ACM2 - API Cost Multiplier 2.0

FastAPI application for research evaluation and cost tracking.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.router import api_router
from .infra.db.session import engine, async_session_factory
from .infra.db.models import Base
from .infra.db.repositories import PresetRepository, DocumentRepository, RunRepository
from .config import get_settings
from .middleware.auth import ApiKeyMiddleware, RateLimitMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting ACM2 API server...")
    
    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
    
    # ORPHAN RECOVERY: Mark any 'running' runs as failed (they were orphaned by server restart)
    async with async_session_factory() as session:
        run_repo = RunRepository(session)
        orphaned_runs = await run_repo.get_active_runs()
        for run in orphaned_runs:
            if run.status == "running":
                logger.warning(f"Marking orphaned run {run.id} as failed (was still 'running' when server started)")
                await run_repo.fail(run.id, error_message="Run orphaned by server restart. The server was restarted while this run was in progress.")
        if orphaned_runs:
            logger.info(f"Orphan recovery complete: marked {len([r for r in orphaned_runs if r.status == 'running'])} orphaned runs as failed")
    
    # Seed default preset
    async with async_session_factory() as session:
        repo = PresetRepository(session)
        doc_repo = DocumentRepository(session)
        existing = await repo.get_by_name("Default Preset")
        if not existing:
            logger.info("Seeding default preset...")
            
            # Read instruction file - no fallback, instructions must be in file or empty
            instructions = ""
            try:
                instr_path = Path("data/defaults/instructions.md")
                if instr_path.exists():
                    instructions = instr_path.read_text(encoding="utf-8")
                else:
                    logger.warning("No instructions.md file found at data/defaults/instructions.md")
            except Exception as e:
                logger.error(f"Failed to read instructions file: {e}")
            
            # Create default document in database
            sample_input_path = "data/defaults/sample_input.txt"
            sample_doc = await doc_repo.get_by_path(sample_input_path)
            if not sample_doc:
                try:
                    sample_path = Path(sample_input_path)
                    if sample_path.exists():
                        sample_content = sample_path.read_text(encoding="utf-8")
                    else:
                        sample_content = "Sample input document content."
                    sample_doc = await doc_repo.create(
                        name="sample_input.txt",
                        path=sample_input_path,
                        content=sample_content,
                        file_type="txt",
                        size_bytes=len(sample_content.encode('utf-8'))
                    )
                    logger.info(f"Created default document: {sample_doc.id}")
                except Exception as e:
                    logger.error(f"Failed to create default document: {e}")

            # Create default preset
            await repo.create(
                name="Default Preset",
                description="A default preset with sample input and instructions.",
                documents=[sample_doc.id if sample_doc else sample_input_path],
                models=[{"provider": "openai", "model": "gpt-5", "temperature": 0.7, "max_tokens": 4000}],
                generators=["fpf"],
                iterations=1,
                evaluation_enabled=True,
                pairwise_enabled=False,
                fpf_config={"prompt_template": instructions},
                gptr_config=None
            )
            logger.info("Default preset created.")
    
    # Startup complete
    yield
    
    # Shutdown
    await engine.dispose()
    logger.info("Shutting down ACM2 API server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    print(f"!!! USING DATABASE URL: {settings.database_url} !!!")
    
    app = FastAPI(
        title="ACM2 - API Cost Multiplier",
        description="Research evaluation and cost tracking platform",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite default
            "http://localhost:5174",  # Vite alternate
            "http://localhost:3000",  # Common React port
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API key auth + simple per-key rate limiting
    app.add_middleware(
        RateLimitMiddleware,
        api_key=settings.api_key,
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(ApiKeyMiddleware, api_key=settings.api_key)
    
    # Include API routes
    app.include_router(api_router)
    
    # ---------------------------------------------------------------------
    # Static UI (SPA)
    #
    # Prefer the Vite build output at acm2/acm2/ui/dist if present, otherwise
    # fall back to the legacy committed directory at acm2/acm2/app/static.
    # This avoids the common "I changed the UI but nothing changed" issue when
    # the backend is still serving old prebuilt assets.
    # ---------------------------------------------------------------------
    project_root = Path(__file__).resolve().parent.parent  # acm2/acm2
    ui_dist_dir = project_root / "ui" / "dist"
    legacy_static_dir = Path(__file__).resolve().parent / "static"

    static_dir = ui_dist_dir if ui_dist_dir.exists() else legacy_static_dir

    if static_dir.exists():
        logger.info("Serving UI static files from: %s", static_dir)
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def spa_index():
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"service": "ACM2", "version": "2.0.0"}

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_router(full_path: str):
            if full_path.startswith(("api", "docs", "redoc", "openapi")):
                raise HTTPException(status_code=404)
            candidate = static_dir / full_path
            if candidate.exists():
                return FileResponse(candidate)
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"service": "ACM2", "version": "2.0.0"}
    else:
        @app.get("/", include_in_schema=False)
        async def dev_root():
            return {
                "name": "ACM2 - API Cost Multiplier",
                "version": "2.0.0",
                "docs": "/docs",
                "api": "/api/v1",
            }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
