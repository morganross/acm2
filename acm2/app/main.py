"""
ACM2 - API Cost Multiplier 2.0

FastAPI application for research evaluation and cost tracking.
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Windows requires ProactorEventLoop for subprocess support (used by FPF adapter)
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from .api.router import api_router
from .infra.db.session import engine, async_session_factory
from .infra.db.models import Base
from .infra.db.repositories import PresetRepository, DocumentRepository, RunRepository
from .config import get_settings
from .db.master import get_master_db
# Per-user auth is now handled per-route via Depends(get_current_user)
# from .middleware.auth import ApiKeyMiddleware, RateLimitMiddleware


class NoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to disable ALL caching on API responses.
    
    CRITICAL: Caching has caused 3 years of "works once, never again" bugs.
    Old cached responses mask code changes, causing developers to stare at
    new code while the browser/proxy serves stale data.
    
    This middleware adds aggressive no-cache headers to EVERY response.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Disable all caching
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        response.headers["X-Accel-Expires"] = "0"  # nginx
        response.headers["Surrogate-Control"] = "no-store"  # CDNs
        return response


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

    settings = get_settings()
    if not settings.seed_preset_id or not settings.seed_version:
        raise RuntimeError("Seed package settings missing: SEED_PRESET_ID and SEED_VERSION are required")
    
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
    
    # NO DEFAULT PRESET SEEDING
    # All presets must be created through the GUI. 
    # The GUI is the ONLY source of truth for presets.
    # No hardcoded defaults, samples, or placeholders are permitted.
    
    # Startup complete
    yield
    
    # Shutdown
    await engine.dispose()
    
    # Close master MySQL pool
    try:
        master_db = await get_master_db()
        await master_db.close()
        logger.info("Master database pool closed")
    except Exception as e:
        logger.warning(f"Error closing master DB pool: {e}")
    
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
            "http://localhost",        # WordPress on port 80
            "http://127.0.0.1",        # WordPress on port 80
            "http://localhost:80",
            "http://127.0.0.1:80",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # NO-CACHE MIDDLEWARE - CRITICAL
    # Caching has caused 3 years of "works once, never again" bugs.
    # This middleware ensures NO API response is ever cached.
    app.add_middleware(NoCacheMiddleware)

    # Per-user authentication is now handled per-route via Depends(get_current_user)
    # The old static API key middleware has been removed.
    # See: acm2/app/auth/middleware.py for the per-user auth implementation
    
    # Include API routes
    app.include_router(api_router)
    
    # Validation error handler - log full details for debugging
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
    
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
            if candidate.exists() and candidate.is_file():
                # Determine media type for proper MIME handling
                suffix = candidate.suffix.lower()
                media_types = {
                    ".js": "application/javascript",
                    ".mjs": "application/javascript",
                    ".css": "text/css",
                    ".html": "text/html",
                    ".json": "application/json",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml",
                    ".ico": "image/x-icon",
                    ".woff": "font/woff",
                    ".woff2": "font/woff2",
                    ".ttf": "font/ttf",
                }
                media_type = media_types.get(suffix)
                return FileResponse(candidate, media_type=media_type)
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
    import sys
    import uvicorn
    
    # Windows requires ProactorEventLoop for subprocess support with reload mode
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
