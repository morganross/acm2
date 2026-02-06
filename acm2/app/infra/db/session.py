"""
Database session management.

Provides both shared database access (for backwards compatibility) and
per-user database sessions for multi-tenant isolation.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import event, text

from app.config import get_settings

settings = get_settings()
print(f"SESSION DB URL: {settings.database_url}")

# Cache for per-user engines to avoid creating new engine for each request
# Keys are now UUID strings, not integers
_user_engines: Dict[str, Any] = {}
_user_session_factories: Dict[str, async_sessionmaker] = {}
_user_schema_valid: Dict[str, bool] = {}


def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and other performance settings for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Enable WAL mode for the shared database
if "sqlite" in settings.database_url:
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session as async context manager."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes - uses SHARED database.
    
    DEPRECATED: Use get_user_db_session() for per-user isolation.
    This still works for backwards compatibility but all data is shared.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _get_user_db_url(user_uuid: str) -> str:
    """Get SQLite database URL for a specific user by UUID."""
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / f"user_{user_uuid}.db"
    return f"sqlite+aiosqlite:///{db_path}"


def _get_user_db_path(user_uuid: str) -> Path:
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"user_{user_uuid}.db"


def _build_user_engine(db_url: str):
    user_engine = create_async_engine(
        db_url,
        echo=settings.debug,
        future=True,
    )
    event.listen(user_engine.sync_engine, "connect", _set_sqlite_pragma)
    return user_engine


async def _has_required_runs_schema(conn) -> bool:
    result = await conn.execute(text("PRAGMA table_info(runs)"))
    columns = {row[1] for row in result.fetchall()}
    return "preset_id" in columns


async def _rebuild_user_db(user_uuid: str) -> None:
    db_path = _get_user_db_path(user_uuid)
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{db_path}{suffix}")
        if path.exists():
            path.unlink()


async def _get_or_create_user_engine(user_uuid: str):
    """Get or create SQLAlchemy engine for a user's database by UUID."""
    if user_uuid not in _user_engines:
        db_url = _get_user_db_url(user_uuid)
        user_engine = _build_user_engine(db_url)

        _user_engines[user_uuid] = user_engine
        _user_session_factories[user_uuid] = async_sessionmaker(
            user_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        # Initialize tables for this user's database
        from app.infra.db.base import Base
        from app.infra.db.models import preset, run, document, artifact, content, github_connection, user_meta, user_settings, api_key  # noqa: F401

        async with user_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    if not _user_schema_valid.get(user_uuid):
        user_engine = _user_engines[user_uuid]
        async with user_engine.begin() as conn:
            is_valid = await _has_required_runs_schema(conn)

        if not is_valid:
            await user_engine.dispose()
            _user_engines.pop(user_uuid, None)
            _user_session_factories.pop(user_uuid, None)
            _user_schema_valid.pop(user_uuid, None)
            await _rebuild_user_db(user_uuid)

            db_url = _get_user_db_url(user_uuid)
            user_engine = _build_user_engine(db_url)
            _user_engines[user_uuid] = user_engine
            _user_session_factories[user_uuid] = async_sessionmaker(
                user_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            from app.infra.db.base import Base
            from app.infra.db.models import preset, run, document, artifact, content, github_connection, user_meta, user_settings  # noqa: F401

            async with user_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with user_engine.begin() as conn:
                is_valid = await _has_required_runs_schema(conn)

            if not is_valid:
                raise RuntimeError("Per-user database schema is invalid after rebuild")

        _user_schema_valid[user_uuid] = True
    
    return _user_engines[user_uuid], _user_session_factories[user_uuid]


@asynccontextmanager
async def get_user_session_by_uuid(user_uuid: str) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for a user by UUID (for background tasks).
    
    Use this in background tasks where you don't have a Request object.
    
    Example:
        async with get_user_session_by_uuid(user_uuid) as session:
            repo = RunRepository(session, user_uuid=user_uuid)
            ...
    """
    _, session_factory = await _get_or_create_user_engine(user_uuid)
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_user_db_session(user: Dict[str, Any]) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for authenticated user (internal use).
    
    This creates/uses a per-user SQLite database at data/user_{uuid}.db.
    All tables (presets, runs, documents, etc.) are created automatically.
    """
    user_uuid = user['uuid']
    _, session_factory = await _get_or_create_user_engine(user_uuid)
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ==============================================================================
# PER-USER DATABASE DEPENDENCY FOR ROUTES
# ==============================================================================
#
# SECURITY: PER-USER DATABASE ISOLATION
# =====================================
# Each authenticated user gets their own SQLite database file at:
#   data/user_{uuid}.db
#
# This provides complete data isolation between users - User A cannot
# access User B's presets, runs, documents, etc. because they are stored
# in separate database files.
#
# The UUID comes from the API key (verified by get_current_user), which
# is linked to a valid user record. This chain of trust ensures:
#   1. API key is validated against user's database
#   2. UUID is extracted from the verified key (not user input)
#   3. UUID determines which SQLite database file to use
#   4. User can only access their own database
#
# Repository classes additionally store user_uuid for audit trails.
#
# Usage pattern in route handlers:
#   from app.infra.db.session import get_user_db
#   from app.auth.middleware import get_current_user
#   
#   @router.get("/presets")
#   async def list_presets(
#       user: dict = Depends(get_current_user),
#       db: AsyncSession = Depends(get_user_db),
#   ):
#       repo = PresetRepository(db, user_uuid=user['uuid'])
#       ...
#
# NOTE: get_user_db extracts user_uuid from request.state.user which is set
# by get_current_user. Make sure get_current_user is called BEFORE get_user_db
# by listing it first in the function signature.
# ==============================================================================

from fastapi import Depends, Request
from fastapi import HTTPException, status
from sqlalchemy import select


async def get_user_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: Get per-user database session.
    
    This reads user_uuid from request.state.user which MUST be set by
    get_current_user before this dependency runs.
    
    Routes should declare dependencies in this order:
        user: dict = Depends(get_current_user),  # First - sets request.state.user
        db: AsyncSession = Depends(get_user_db),  # Second - reads user_uuid
    """
    # Import here to avoid circular imports
    from app.auth.middleware import get_current_user
    
    # Get API key from header
    api_key = request.headers.get('X-ACM2-API-Key')
    if not api_key:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Authenticate and get user
    user = await get_current_user(api_key)
    
    async for session in get_user_db_session(user):
        await _ensure_seed_ready(session, user["uuid"])
        yield session


async def _ensure_seed_ready(session: AsyncSession, user_uuid: str) -> None:
    from app.infra.db.models.user_meta import UserMeta
    from app.db.seed_user import initialize_user

    result = await session.execute(
        select(UserMeta).where(UserMeta.uuid == user_uuid)
    )
    meta = result.scalar_one_or_none()
    if not meta or meta.seed_status != "ready":
        await initialize_user(user_uuid)

        result = await session.execute(
            select(UserMeta).where(UserMeta.uuid == user_uuid)
        )
        meta = result.scalar_one_or_none()
        if not meta or meta.seed_status != "ready":
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail="User setup in progress"
            )


async def init_db() -> None:
    """Initialize database - create all tables."""
    from app.infra.db.base import Base
    # Import all models to register them
    from app.infra.db.models import preset, run, document, artifact, user_meta, user_settings  # noqa: F401
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
