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
_user_engines: Dict[int, Any] = {}
_user_session_factories: Dict[int, async_sessionmaker] = {}


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


def _get_user_db_url(user_id: int) -> str:
    """Get SQLite database URL for a specific user."""
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / f"user_{user_id}.db"
    return f"sqlite+aiosqlite:///{db_path}"


async def _get_or_create_user_engine(user_id: int):
    """Get or create SQLAlchemy engine for a user's database."""
    if user_id not in _user_engines:
        db_url = _get_user_db_url(user_id)
        user_engine = create_async_engine(
            db_url,
            echo=settings.debug,
            future=True,
        )
        # Enable WAL mode for per-user SQLite databases
        event.listen(user_engine.sync_engine, "connect", _set_sqlite_pragma)
        
        _user_engines[user_id] = user_engine
        _user_session_factories[user_id] = async_sessionmaker(
            user_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        # Initialize tables for this user's database
        from app.infra.db.base import Base
        from app.infra.db.models import preset, run, document, artifact, content, github_connection, user_meta, user_settings  # noqa: F401
        
        async with user_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    return _user_engines[user_id], _user_session_factories[user_id]


@asynccontextmanager
async def get_user_session_by_id(user_id: int) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for a user by user_id (for background tasks).
    
    Unlike get_user_db_session, this takes just the user_id int directly.
    Use this in background tasks where you don't have a Request object.
    
    Example:
        async with get_user_session_by_id(user_id) as session:
            repo = RunRepository(session, user_id=user_id)
            ...
    """
    _, session_factory = await _get_or_create_user_engine(user_id)
    
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
    
    This creates/uses a per-user SQLite database at data/user_{id}.db.
    All tables (presets, runs, documents, etc.) are created automatically.
    """
    user_id = user['id']
    _, session_factory = await _get_or_create_user_engine(user_id)
    
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
#   data/user_{id}.db
#
# This provides complete data isolation between users - User A cannot
# access User B's presets, runs, documents, etc. because they are stored
# in separate database files.
#
# The user_id comes from the JWT token (verified by get_current_user), which
# is linked to a valid user record in the master MySQL database. This chain
# of trust ensures:
#   1. API key/JWT is validated against master DB
#   2. user_id is extracted from the verified token (not user input)
#   3. user_id determines which SQLite database file to use
#   4. User can only access their own database
#
# Repository classes additionally store user_id for audit trails and
# potential future cross-user queries by admin users.
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
#       repo = PresetRepository(db, user_id=user['id'])
#       ...
#
# NOTE: get_user_db extracts user_id from request.state.user which is set
# by get_current_user. Make sure get_current_user is called BEFORE get_user_db
# by listing it first in the function signature.
# ==============================================================================

from fastapi import Depends, Request
from fastapi import HTTPException, status
from sqlalchemy import select


async def get_user_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: Get per-user database session.
    
    This reads user_id from request.state.user which MUST be set by
    get_current_user before this dependency runs.
    
    Routes should declare dependencies in this order:
        user: dict = Depends(get_current_user),  # First - sets request.state.user
        db: AsyncSession = Depends(get_user_db),  # Second - reads user_id
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
        await _ensure_seed_ready(session, user["id"])
        yield session


async def _ensure_seed_ready(session: AsyncSession, user_id: int) -> None:
    from app.infra.db.models.user_meta import UserMeta

    result = await session.execute(
        select(UserMeta).where(UserMeta.user_id == user_id)
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
