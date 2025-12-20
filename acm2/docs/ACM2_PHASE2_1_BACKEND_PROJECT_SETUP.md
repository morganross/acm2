# ACM 2.0 – Phase 2.1 Backend Project Setup

## 1. Purpose

Phase 2.1 establishes the **foundational backend project structure** for ACM 2.0. This phase creates a new FastAPI service with proper configuration, logging, database connectivity, and a health check endpoint. No business logic—just the skeleton that all subsequent phases build upon.

## 2. Scope

- Create project directory structure under `acm2/`
- Set up Python package with `pyproject.toml`
- Configure FastAPI application factory
- Implement structured logging
- Set up database connection (PostgreSQL + SQLite fallback)
- Create health check endpoint
- Configure development tooling (linting, formatting, type checking)
- Write initial tests and CI pipeline

## 3. Project Structure

```
acm2/
├── pyproject.toml                 # Package definition, dependencies, tools
├── alembic.ini                    # Database migrations config
├── Makefile                       # Task runner (cross-platform via make)
├── .env.example                   # Environment variable template
├── .gitignore
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Pydantic settings
│   │
│   ├── api/                       # HTTP layer
│   │   ├── __init__.py
│   │   ├── router.py              # Main router aggregating all routes
│   │   ├── health.py              # Health check endpoint
│   │   ├── runs.py                # (Phase 2.2)
│   │   ├── documents.py           # (Phase 2.2)
│   │   └── artifacts.py           # (Phase 2.2)
│   │
│   ├── domain/                    # Business logic layer
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic domain models
│   │   └── exceptions.py          # Domain exceptions
│   │
│   ├── services/                  # Application services
│   │   ├── __init__.py
│   │   └── health_service.py
│   │
│   ├── infra/                     # Infrastructure layer
│   │   ├── __init__.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py         # Database session management
│   │   │   ├── models.py          # SQLAlchemy ORM models
│   │   │   └── repositories/      # Data access layer
│   │   │       └── __init__.py
│   │   ├── logging.py             # Structured logging setup
│   │   └── telemetry.py           # OpenTelemetry (optional)
│   │
│   └── middleware/
│       ├── __init__.py
│       ├── request_id.py          # X-Request-ID injection
│       └── error_handler.py       # Global exception handling
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_health.py
│   └── integration/
│       └── __init__.py
│
├── scripts/
│   ├── check_line_length.py       # Enforce <800 lines rule
│   └── run_dev.py                 # Development server launcher
│
└── docs/
    ├── setup.md                   # Developer setup guide
    └── adr/
        └── 0001-project-structure.md
```

## 4. Dependencies

### 4.1 pyproject.toml

```toml
[project]
name = "acm2"
version = "0.1.0"
description = "Advanced Comparison Manager 2.0 - API Backend"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Morgan", email = "morgan@example.com"}
]

dependencies = [
    # Web framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    
    # Database
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",           # PostgreSQL async driver
    "aiosqlite>=0.19.0",         # SQLite async driver
    "alembic>=1.13.0",           # Migrations
    
    # Configuration & validation
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    
    # HTTP client (for GitHub API)
    "httpx>=0.26.0",
    
    # Utilities
    "python-ulid>=2.2.0",        # ULID generation
    "structlog>=24.1.0",         # Structured logging
    "orjson>=3.9.0",             # Fast JSON
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.26.0",             # For TestClient
    
    # Linting & formatting
    "ruff>=0.1.0",
    "black>=24.1.0",
    "mypy>=1.8.0",
    
    # Type stubs
    "types-orjson>=3.6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=app --cov-report=term-missing"
```

## 5. Configuration

### 5.1 app/config.py

```python
"""
Application configuration via environment variables.

Uses pydantic-settings for type-safe configuration loading.
All secrets should be provided via environment variables, never hardcoded.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="ACM2_DB_")
    
    # Database selection
    use_sqlite: bool = Field(
        default=False,
        description="Use SQLite instead of PostgreSQL"
    )
    
    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "acm2"
    postgres_password: str = ""
    postgres_database: str = "acm2"
    
    # SQLite settings
    sqlite_path: str = "./acm2.db"
    
    # Connection pool
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800
    echo_sql: bool = False
    
    @property
    def async_url(self) -> str:
        """Get async database URL."""
        if self.use_sqlite:
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )
    
    @property
    def sync_url(self) -> str:
        """Get sync database URL (for Alembic)."""
        if self.use_sqlite:
            return f"sqlite:///{self.sqlite_path}"
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )


class GitHubSettings(BaseSettings):
    """GitHub API configuration."""
    
    model_config = SettingsConfigDict(env_prefix="ACM2_GITHUB_")
    
    token: str = Field(default="", description="GitHub Personal Access Token")
    app_id: str | None = None
    app_private_key_path: str | None = None
    
    # Default repositories
    default_docs_repo: str = ""
    default_outputs_repo: str = ""
    default_logs_repo: str = ""


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    model_config = SettingsConfigDict(env_prefix="ACM2_LOG_")
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "console"] = "json"
    include_timestamp: bool = True


class Settings(BaseSettings):
    """Root application settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="ACM2_",
        env_nested_delimiter="__",
        extra="ignore"
    )
    
    # Application
    app_name: str = "ACM 2.0 API"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # API
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True
    
    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    
    @field_validator("debug", mode="before")
    @classmethod
    def set_debug_from_env(cls, v: bool, info) -> bool:
        """Auto-enable debug in development."""
        if info.data.get("environment") == "development":
            return True
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### 5.2 .env.example

```bash
# Application
ACM2_ENVIRONMENT=development
ACM2_DEBUG=true
ACM2_HOST=0.0.0.0
ACM2_PORT=8000

# Database (PostgreSQL)
ACM2_DB_USE_SQLITE=false
ACM2_DB_POSTGRES_HOST=localhost
ACM2_DB_POSTGRES_PORT=5432
ACM2_DB_POSTGRES_USER=acm2
ACM2_DB_POSTGRES_PASSWORD=your_password_here
ACM2_DB_POSTGRES_DATABASE=acm2

# Database (SQLite alternative)
# ACM2_DB_USE_SQLITE=true
# ACM2_DB_SQLITE_PATH=./acm2.db

# GitHub
ACM2_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
ACM2_GITHUB_DEFAULT_DOCS_REPO=YOUR_USER/acm-docs
ACM2_GITHUB_DEFAULT_OUTPUTS_REPO=YOUR_USER/acm-outputs
ACM2_GITHUB_DEFAULT_LOGS_REPO=YOUR_USER/acm-logs

# Logging
ACM2_LOG_LEVEL=INFO
ACM2_LOG_FORMAT=json
```

## 6. Application Factory

### 6.1 app/main.py

```python
"""
FastAPI application factory.

Creates and configures the ACM 2.0 API application.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.infra.db.session import DatabaseManager
from app.infra.logging import setup_logging, get_logger
from app.middleware.error_handler import setup_exception_handlers
from app.middleware.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    logger = get_logger(__name__)
    settings = get_settings()
    
    # Startup
    logger.info(
        "Starting ACM 2.0 API",
        environment=settings.environment,
        version=settings.app_version
    )
    
    # Initialize database
    db_manager = DatabaseManager(settings.database)
    app.state.db = db_manager
    
    # Verify database connection
    if await db_manager.health_check():
        logger.info("Database connection established")
        
        # --- STARTUP RECOVERY ---
        # Reset runs that were left 'running' when the server stopped.
        # This prevents "zombie" runs since we don't use an external task queue.
        try:
            # Note: These imports depend on Step 2.7 implementation
            from sqlalchemy import update, func
            from app.infra.db.models.run import RunModel
            
            async with db_manager.session() as session:
                stmt = (
                    update(RunModel)
                    .where(RunModel.status == "running")
                    .values(
                        status="failed",
                        summary="System restarted during execution (Zombie Run Recovery)",
                        completed_at=func.now()
                    )
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount > 0:
                    logger.warning(
                        "Startup Recovery: Reset stuck runs",
                        count=result.rowcount
                    )
        except ImportError:
            # RunModel might not exist yet in early dev stages
            logger.debug("Startup Recovery skipped (RunModel not found)")
        except Exception as e:
            logger.error("Startup Recovery failed", error=str(e))
        # ------------------------
    else:
        logger.error("Database connection failed")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ACM 2.0 API")
    await db_manager.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Args:
        settings: Optional settings override (useful for testing)
    
    Returns:
        Configured FastAPI application
    """
    if settings is None:
        settings = get_settings()
    
    # Setup logging first
    setup_logging(settings.logging)
    
    # Create app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Advanced Comparison Manager 2.0 API",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan
    )
    
    # Store settings in app state
    app.state.settings = settings
    
    # Add middleware
    app.add_middleware(RequestIDMiddleware)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Include routers
    app.include_router(api_router, prefix=settings.api_prefix)
    
    return app


# Default app instance for uvicorn
app = create_app()
```

## 7. Logging

### 7.1 app/infra/logging.py

```python
"""
Structured logging configuration using structlog.

Provides consistent, structured logs in JSON or console format.
"""
import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import LoggingSettings


def setup_logging(settings: LoggingSettings) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        settings: Logging configuration
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.level)
    )
    
    # Shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.include_timestamp:
        shared_processors.insert(0, structlog.processors.TimeStamper(fmt="iso"))
    
    # Format-specific processors
    if settings.format == "json":
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to all subsequent log calls in this context.
    
    Useful for adding request_id, run_id, etc.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
```

## 8. Database Session

### 8.1 app/infra/db/session.py

```python
"""
Database session management with SQLAlchemy 2.0 async.

Provides connection pooling and session lifecycle management.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import DatabaseSettings
from app.infra.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.
    
    Provides async context manager for transactional sessions.
    """
    
    def __init__(self, settings: DatabaseSettings) -> None:
        """
        Initialize database manager.
        
        Args:
            settings: Database configuration
        """
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    @property
    def engine(self) -> AsyncEngine:
        """Get or create async engine."""
        if self._engine is None:
            self._engine = create_async_engine(
                self.settings.async_url,
                pool_size=self.settings.pool_size,
                max_overflow=self.settings.max_overflow,
                pool_timeout=self.settings.pool_timeout,
                pool_recycle=self.settings.pool_recycle,
                echo=self.settings.echo_sql,
            )
        return self._engine
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create session factory."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Provide a transactional scope around a series of operations.
        
        Automatically commits on success, rolls back on exception.
        
        Usage:
            async with db_manager.session() as session:
                session.add(entity)
                # commits automatically on exit
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> bool:
        """
        Verify database connectivity.
        
        Returns:
            True if database is reachable, False otherwise
        """
        try:
            async with self.session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    async def close(self) -> None:
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")
```

## 9. API Router & Health Check

### 9.1 app/api/router.py

```python
"""
Main API router aggregating all endpoint routers.
"""
from fastapi import APIRouter

from app.api.health import router as health_router

api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])

# Future routers (Phase 2.2+)
# api_router.include_router(runs_router, prefix="/runs", tags=["runs"])
# api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
# api_router.include_router(artifacts_router, prefix="/artifacts", tags=["artifacts"])
```

### 9.2 app/api/health.py

```python
"""
Health check endpoint.

Provides service health status including database connectivity.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.infra.db.session import DatabaseManager

router = APIRouter()


class HealthCheckResult(BaseModel):
    """Individual health check result."""
    
    status: Literal["ok", "error"]
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: Literal["healthy", "degraded", "unhealthy"]
    service: str
    version: str
    timestamp: str
    checks: dict[str, HealthCheckResult]


def get_db(request: Request) -> DatabaseManager:
    """Dependency to get database manager from app state."""
    return request.app.state.db


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    db: DatabaseManager = Depends(get_db)
) -> HealthResponse:
    """
    Check service health.
    
    Returns overall status and individual component checks.
    """
    settings = request.app.state.settings
    checks: dict[str, HealthCheckResult] = {}
    
    # Database check
    db_healthy = await db.health_check()
    checks["database"] = HealthCheckResult(
        status="ok" if db_healthy else "error",
        message=None if db_healthy else "Connection failed"
    )
    
    # Determine overall status
    all_ok = all(c.status == "ok" for c in checks.values())
    any_ok = any(c.status == "ok" for c in checks.values())
    
    if all_ok:
        status = "healthy"
    elif any_ok:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return HealthResponse(
        status=status,
        service="acm2-api",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks
    )


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe.
    
    Returns 200 if the service is running.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(db: DatabaseManager = Depends(get_db)) -> dict[str, str]:
    """
    Kubernetes readiness probe.
    
    Returns 200 if the service is ready to accept requests.
    """
    if await db.health_check():
        return {"status": "ready"}
    
    # Return 503 via exception if not ready
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail="Service not ready")
```

## 10. Middleware

### 10.1 app/middleware/request_id.py

```python
"""
Request ID middleware.

Injects X-Request-ID header for request tracing.
"""
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.infra.logging import bind_context, clear_context


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a unique ID.
    
    - Uses client-provided X-Request-ID if present
    - Generates UUID if not provided
    - Adds ID to response headers
    - Binds ID to logging context
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response]
    ) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Bind to logging context
        bind_context(request_id=request_id)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Add to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        finally:
            # Clear logging context
            clear_context()
```

### 10.2 app/middleware/error_handler.py

```python
"""
Global exception handling.

Converts exceptions to consistent JSON error responses.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.infra.logging import get_logger

logger = get_logger(__name__)


class ErrorDetail(BaseModel):
    """Error detail structure."""
    
    field: str | None = None
    message: str
    value: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    
    error: dict


def setup_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""
    
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")
        
        logger.error(
            "Unhandled exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": request_id
                }
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError
    ) -> JSONResponse:
        """Handle validation errors."""
        request_id = getattr(request.state, "request_id", "unknown")
        
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "request_id": request_id
                }
            }
        )
```

## 11. Scripts

### 11.1 scripts/check_line_length.py

```python
#!/usr/bin/env python3
"""
Enforce maximum line count per file.

Morgan's Rule: No file over 800 lines.
"""
import sys
from pathlib import Path

MAX_LINES = 800
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "alembic"}
INCLUDE_EXTENSIONS = {".py"}


def check_file(path: Path) -> tuple[bool, int]:
    """
    Check if file exceeds line limit.
    
    Returns: (is_ok, line_count)
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        return line_count <= MAX_LINES, line_count
    except Exception as e:
        print(f"Warning: Could not read {path}: {e}")
        return True, 0


def main() -> int:
    """Run line length check on all Python files."""
    root = Path(__file__).parent.parent / "app"
    
    if not root.exists():
        print(f"Error: Directory not found: {root}")
        return 1
    
    violations: list[tuple[Path, int]] = []
    
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in INCLUDE_EXTENSIONS:
            # Skip excluded directories
            if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
                continue
            
            is_ok, line_count = check_file(path)
            if not is_ok:
                violations.append((path, line_count))
    
    if violations:
        print(f"\n❌ {len(violations)} file(s) exceed {MAX_LINES} lines:\n")
        for path, count in sorted(violations, key=lambda x: -x[1]):
            print(f"  {path}: {count} lines")
        print(f"\nMax allowed: {MAX_LINES} lines per file")
        return 1
    
    print(f"✓ All files under {MAX_LINES} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 11.2 scripts/run_dev.py

```python
#!/usr/bin/env python3
"""
Development server launcher.
"""
import uvicorn

from app.config import get_settings


def main() -> None:
    """Run development server with auto-reload."""
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
```

## 12. Makefile

```makefile
.PHONY: install dev test lint format typecheck check run migrate

# Install dependencies
install:
	pip install -e ".[dev]"

# Run development server
dev:
	python scripts/run_dev.py

# Run tests
test:
	pytest tests/ -v --cov=app --cov-report=term-missing

# Run linting
lint:
	ruff check app/ tests/
	python scripts/check_line_length.py

# Format code
format:
	black app/ tests/
	ruff check --fix app/ tests/

# Type checking
typecheck:
	mypy app/

# Run all checks (CI)
check: lint typecheck test

# Run database migrations
migrate:
	alembic upgrade head

# Create new migration
migration:
	alembic revision --autogenerate -m "$(msg)"

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
```

## 13. Tests

### 13.1 tests/conftest.py

```python
"""
Pytest fixtures for ACM 2.0 tests.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, DatabaseSettings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with SQLite."""
    return Settings(
        environment="development",
        debug=True,
        database=DatabaseSettings(
            use_sqlite=True,
            sqlite_path=":memory:"
        )
    )


@pytest.fixture
async def app(test_settings: Settings):
    """Create test application."""
    return create_app(test_settings)


@pytest.fixture
async def client(app) -> AsyncClient:
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### 13.2 tests/test_health.py

```python
"""
Health endpoint tests.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health endpoint returns valid response."""
    response = await client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["service"] == "acm2-api"
    assert "version" in data
    assert "timestamp" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient) -> None:
    """Test liveness endpoint."""
    response = await client.get("/api/v1/health/live")
    
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    """Test X-Request-ID is returned."""
    response = await client.get("/api/v1/health")
    
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_custom_request_id(client: AsyncClient) -> None:
    """Test custom X-Request-ID is echoed."""
    custom_id = "test-request-123"
    response = await client.get(
        "/api/v1/health",
        headers={"X-Request-ID": custom_id}
    )
    
    assert response.headers["X-Request-ID"] == custom_id
```

## 14. Developer Setup Guide

### 14.1 docs/setup.md

```markdown
# ACM 2.0 Developer Setup

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or use SQLite for local development)
- Git

## Quick Start

1. **Clone and navigate:**
   ```bash
   cd acm2
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Unix
   ```

3. **Install dependencies:**
   ```bash
   make install
   # or: pip install -e ".[dev]"
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run database migrations:**
   ```bash
   make migrate
   ```

6. **Start development server:**
   ```bash
   make dev
   # or: python scripts/run_dev.py
   ```

7. **Access API:**
   - API: http://localhost:8000/api/v1/health
   - Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Running Tests

```bash
make test
```

## Code Quality

```bash
make check  # Run all checks (lint, typecheck, test)
make format # Auto-format code
```

## Using SQLite (Simpler Setup)

Set in `.env`:
```bash
ACM2_DB_USE_SQLITE=true
ACM2_DB_SQLITE_PATH=./acm2.db
```
```

## 15. Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-01 | `make dev` starts server successfully | Manual test |
| SC-02 | `/api/v1/health` returns 200 with valid JSON | `curl` or browser |
| SC-03 | Database health check passes | Health response shows `database: ok` |
| SC-04 | `make check` passes (lint + types + tests) | CI pipeline |
| SC-05 | All files under 800 lines | `python scripts/check_line_length.py` |
| SC-06 | X-Request-ID header works | Test passes |

## 16. Next Steps

After Phase 2.1 is complete:
- **Phase 2.2**: Implement Run and Document APIs
- **Phase 2.3**: Implement StorageProvider abstraction
- **Phase 2.4**: Add Artifact APIs
