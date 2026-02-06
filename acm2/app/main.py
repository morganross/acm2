"""
ACM2 - API Cost Multiplier 2.0

FastAPI application for research evaluation and cost tracking.
"""
import logging
import os
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
from .infra.db.session import engine, get_user_session_by_uuid
from .infra.db.models import Base
from .infra.db.repositories import PresetRepository, DocumentRepository, RunRepository
from .config import get_settings
from .auth.user_registry import load_registry, get_all_user_uuids
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


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    """
    Middleware to normalize trailing slashes.
    
    Strips trailing slashes from all requests (except root "/") BEFORE routing.
    This ensures both /api/v1/provider-keys and /api/v1/provider-keys/ work
    without 307 redirects that cause browsers to lose headers.
    
    Combined with redirect_slashes=False on the FastAPI app, this handles
    any slash variation consistently.
    """
    async def dispatch(self, request: Request, call_next):
        # Strip trailing slash from path (except for root "/")
        path = request.scope["path"]
        if path != "/" and path.endswith("/"):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)


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
    
    # Load user registry from filesystem (scan for user_*.db files)
    logger.info("Loading user registry from filesystem...")
    user_count = load_registry()
    logger.info(f"User registry loaded: {user_count} users found")
    
    # Verify seed database exists
    if not settings.seed_database_path.exists():
        logger.warning(f"Seed database not found at {settings.seed_database_path} - new users will not be seeded!")
    else:
        logger.info(f"Seed database found at {settings.seed_database_path}")
    
    # ORPHAN RECOVERY: Mark any 'running' runs as failed (they were orphaned by server restart)
    # Iterate over all per-user databases since runs are stored per-user.
    all_user_uuids = get_all_user_uuids()
    total_orphaned = 0
    for user_uuid in all_user_uuids:
        try:
            async with get_user_session_by_uuid(user_uuid) as session:
                run_repo = RunRepository(session, user_uuid=user_uuid)
                orphaned_runs = await run_repo.get_active_runs()
                for run in orphaned_runs:
                    if run.status == "running":
                        logger.warning(f"Marking orphaned run {run.id} (user {user_uuid}) as failed")
                        await run_repo.fail(run.id, error_message="Run orphaned by server restart. The server was restarted while this run was in progress.")
                        total_orphaned += 1
        except Exception as e:
            logger.warning(f"Failed to check orphaned runs for user {user_uuid}: {e}")
    
    if total_orphaned > 0:
        logger.info(f"Orphan recovery complete: marked {total_orphaned} orphaned runs as failed")
    
    # Seeding is now handled per-user via seed.db when users access the API
    # See app/db/seed_user.py for the seeding logic
    
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
        redirect_slashes=False,  # Disable 307 redirects - TrailingSlashMiddleware handles normalization
    )
    
    # CORS middleware for frontend
    # Additional origins can be added via ACM2_CORS_ORIGINS env var (comma-separated)
    cors_origins = [
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite alternate
        "http://localhost:3000",  # Common React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost",        # WordPress on port 80
        "http://127.0.0.1",        # WordPress on port 80
        "http://localhost:80",
        "http://127.0.0.1:80",
        # Production WordPress frontend
        "http://16.145.206.59",
        "https://16.145.206.59",
        # Production domain (Cloudflare)
        "https://apicostx.com",
        "https://www.apicostx.com",
    ]
    # Add any custom origins from environment (for production deployment)
    extra_origins = os.environ.get("ACM2_CORS_ORIGINS", "")
    if extra_origins:
        cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # TRAILING SLASH MIDDLEWARE - CRITICAL
    # Normalizes /path/ to /path so both work without 307 redirects.
    # 307 redirects cause browsers to lose headers (like X-ACM2-API-Key).
    app.add_middleware(TrailingSlashMiddleware)
    
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
    
    # Generic exception handler - log full traceback for debugging
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[UNHANDLED EXCEPTION] {request.method} {request.url.path}")
        logger.error(f"[UNHANDLED EXCEPTION] Exception type: {type(exc).__name__}")
        logger.error(f"[UNHANDLED EXCEPTION] Exception message: {str(exc)}")
        logger.error(f"[UNHANDLED EXCEPTION] Full traceback:\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"},
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
    
    # Port 443 is hard-coded and cannot be changed
    ACM2_PORT = 443
    print(f"Starting ACM2 server on https://0.0.0.0:{ACM2_PORT}")
    print("Port 443 is programmatically enforced and cannot be overridden.")
    uvicorn.run("app.main:app", host="0.0.0.0", port=ACM2_PORT, reload=False)
