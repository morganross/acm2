"""
Master Database Manager (SQLite)
Handles user accounts and API key lookups.
Local to backend - no network connection needed.

EXTREME LOGGING ENABLED - every operation is logged in detail.
"""
import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import traceback
import os

logger = logging.getLogger(__name__)

# Path to master database (relative to app root)
MASTER_DB_PATH = Path(__file__).parent.parent.parent / "data" / "master.db"


class MasterDB:
    """Manages master database with user accounts and API keys."""
    
    def __init__(self):
        logger.info("[MASTER_DB] ========================================")
        logger.info("[MASTER_DB] MasterDB.__init__() called")
        logger.info("[MASTER_DB] ========================================")
        logger.info(f"[MASTER_DB] Database path will be: {MASTER_DB_PATH}")
        logger.info(f"[MASTER_DB] Database path exists: {MASTER_DB_PATH.exists()}")
        logger.info(f"[MASTER_DB] Database parent dir: {MASTER_DB_PATH.parent}")
        logger.info(f"[MASTER_DB] Database parent exists: {MASTER_DB_PATH.parent.exists()}")
        self._initialized = False
        logger.info("[MASTER_DB] MasterDB instance created, _initialized = False")
    
    async def _ensure_initialized(self):
        """Ensure database schema is initialized."""
        if not self._initialized:
            logger.info("[MASTER_DB] _ensure_initialized() - First time, creating schema...")
            # Ensure data directory exists
            MASTER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                await self._init_schema(conn)
            self._initialized = True
            logger.info("[MASTER_DB] _ensure_initialized() - Schema created and committed")
    
    async def _init_schema(self, conn: aiosqlite.Connection):
        """Create tables if they don't exist."""
        logger.info("[MASTER_DB] _init_schema() called")
        logger.info("[MASTER_DB] About to execute CREATE TABLE statements...")
        
        try:
            schema_sql = '''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wordpress_user_id INTEGER UNIQUE,
                    username TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    key_prefix TEXT NOT NULL,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    revoked_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
                CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
                CREATE INDEX IF NOT EXISTS idx_users_wordpress ON users(wordpress_user_id);
            '''
            logger.info("[MASTER_DB] Executing schema SQL...")
            await conn.executescript(schema_sql)
            logger.info("[MASTER_DB] Schema SQL executed, committing...")
            await conn.commit()
            logger.info(f"[MASTER_DB] Schema committed. Database file: {MASTER_DB_PATH}")
            logger.info(f"[MASTER_DB] Master database initialized at {MASTER_DB_PATH}")
            
        except Exception as e:
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.error("[MASTER_DB] FATAL ERROR in _init_schema()")
            logger.error(f"[MASTER_DB] Exception type: {type(e).__name__}")
            logger.error(f"[MASTER_DB] Exception message: {str(e)}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            raise
    
    async def create_user(self, username: str, email: str,
                         wordpress_user_id: Optional[int] = None) -> int:
        """Create a new user."""
        logger.info("[MASTER_DB] ========================================")
        logger.info("[MASTER_DB] create_user() called")
        logger.info("[MASTER_DB] ========================================")
        logger.info(f"[MASTER_DB] Input parameters:")
        logger.info(f"[MASTER_DB]   username = {repr(username)}")
        logger.info(f"[MASTER_DB]   email = {repr(email)}")
        logger.info(f"[MASTER_DB]   wordpress_user_id = {repr(wordpress_user_id)}")
        
        try:
            await self._ensure_initialized()
            logger.info("[MASTER_DB] Opening database connection...")
            
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                logger.info("[MASTER_DB] Connection opened, executing INSERT...")
                
                sql = "INSERT INTO users (username, email, wordpress_user_id) VALUES (?, ?, ?)"
                params = (username, email, wordpress_user_id)
                logger.info(f"[MASTER_DB] SQL: {sql}")
                logger.info(f"[MASTER_DB] Params: {params}")
                
                cursor = await conn.execute(sql, params)
                logger.info(f"[MASTER_DB] INSERT executed, cursor = {cursor}")
                
                logger.info("[MASTER_DB] Committing transaction...")
                await conn.commit()
                logger.info("[MASTER_DB] Transaction committed")
                
                user_id = cursor.lastrowid
                logger.info(f"[MASTER_DB] New user ID (lastrowid) = {user_id}")
                
                # Verify the user was created
                logger.info("[MASTER_DB] Verifying user was created by re-reading...")
                verify_cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                verify_row = await verify_cursor.fetchone()
                if verify_row:
                    logger.info(f"[MASTER_DB] Verified: User exists with data: {dict(verify_row)}")
                else:
                    logger.error("[MASTER_DB] VERIFICATION FAILED: User not found after insert!")
                
                logger.info(f"[MASTER_DB] create_user() SUCCESS: Created user '{username}' with ID {user_id}")
                return user_id
                
        except Exception as e:
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.error("[MASTER_DB] FATAL ERROR in create_user()")
            logger.error(f"[MASTER_DB] Exception type: {type(e).__name__}")
            logger.error(f"[MASTER_DB] Exception message: {str(e)}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            raise
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        logger.info(f"[MASTER_DB] get_user_by_id({user_id}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                )
                row = await cursor.fetchone()
                result = dict(row) if row else None
                logger.info(f"[MASTER_DB] get_user_by_id({user_id}) result: {result}")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in get_user_by_id({user_id}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def get_user_by_wordpress_id(self, wordpress_id: int) -> Optional[Dict[str, Any]]:
        """Get user by WordPress user ID."""
        logger.info(f"[MASTER_DB] get_user_by_wordpress_id({wordpress_id}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE wordpress_user_id = ?",
                    (wordpress_id,)
                )
                row = await cursor.fetchone()
                result = dict(row) if row else None
                logger.info(f"[MASTER_DB] get_user_by_wordpress_id({wordpress_id}) result: {result}")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in get_user_by_wordpress_id({wordpress_id}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address."""
        logger.info(f"[MASTER_DB] get_user_by_email({email}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                )
                row = await cursor.fetchone()
                result = dict(row) if row else None
                logger.info(f"[MASTER_DB] get_user_by_email({email}) result: {result}")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in get_user_by_email({email}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def create_api_key(self, user_id: int, key_hash: str,
                           key_prefix: str, name: Optional[str] = None) -> int:
        """Store API key for user."""
        logger.info("[MASTER_DB] ========================================")
        logger.info("[MASTER_DB] create_api_key() called")
        logger.info("[MASTER_DB] ========================================")
        logger.info(f"[MASTER_DB] Input parameters:")
        logger.info(f"[MASTER_DB]   user_id = {user_id}")
        logger.info(f"[MASTER_DB]   key_hash = {key_hash[:20]}... (length: {len(key_hash)})")
        logger.info(f"[MASTER_DB]   key_prefix = {key_prefix}")
        logger.info(f"[MASTER_DB]   name = {name}")
        
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                sql = "INSERT INTO api_keys (user_id, key_hash, key_prefix, name) VALUES (?, ?, ?, ?)"
                params = (user_id, key_hash, key_prefix, name)
                logger.info(f"[MASTER_DB] Executing: {sql}")
                
                cursor = await conn.execute(sql, params)
                await conn.commit()
                key_id = cursor.lastrowid
                
                logger.info(f"[MASTER_DB] create_api_key() SUCCESS: Created key ID {key_id} for user {user_id}")
                return key_id
                
        except Exception as e:
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.error("[MASTER_DB] FATAL ERROR in create_api_key()")
            logger.error(f"[MASTER_DB] Exception type: {type(e).__name__}")
            logger.error(f"[MASTER_DB] Exception message: {str(e)}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            raise
    
    async def get_user_by_key_prefix(self, key_prefix: str) -> Optional[tuple]:
        """Get (key_hash, user_id) by key prefix for auth lookup."""
        logger.info(f"[MASTER_DB] get_user_by_key_prefix({key_prefix}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT key_hash, user_id FROM api_keys WHERE key_prefix = ? AND revoked_at IS NULL",
                    (key_prefix,)
                )
                row = await cursor.fetchone()
                result = (row['key_hash'], row['user_id']) if row else None
                logger.info(f"[MASTER_DB] get_user_by_key_prefix({key_prefix}) result: {'found' if result else 'not found'}")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in get_user_by_key_prefix({key_prefix}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def get_user_by_api_key_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user by API key hash."""
        logger.info(f"[MASTER_DB] get_user_by_api_key_hash() called (hash prefix: {key_hash[:20]}...)")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    """SELECT u.* FROM users u
                       JOIN api_keys k ON u.id = k.user_id
                       WHERE k.key_hash = ? AND k.revoked_at IS NULL""",
                    (key_hash,)
                )
                row = await cursor.fetchone()
                
                if row:
                    # Update last_used_at
                    await conn.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                        (datetime.utcnow().isoformat(), key_hash)
                    )
                    await conn.commit()
                    result = dict(row)
                    logger.info(f"[MASTER_DB] get_user_by_api_key_hash() found user: {result}")
                    return result
                    
                logger.info("[MASTER_DB] get_user_by_api_key_hash() - no user found")
                return None
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in get_user_by_api_key_hash(): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def revoke_api_key(self, key_id: int):
        """Revoke an API key."""
        logger.info(f"[MASTER_DB] revoke_api_key({key_id}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                await conn.execute(
                    "UPDATE api_keys SET revoked_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), key_id)
                )
                await conn.commit()
                logger.info(f"[MASTER_DB] revoke_api_key({key_id}) SUCCESS")
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in revoke_api_key({key_id}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise
    
    async def list_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        logger.info(f"[MASTER_DB] list_user_api_keys({user_id}) called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    """SELECT id, key_prefix, name, created_at, last_used_at, revoked_at
                       FROM api_keys
                       WHERE user_id = ?
                       ORDER BY created_at DESC""",
                    (user_id,)
                )
                rows = await cursor.fetchall()
                result = [dict(row) for row in rows]
                logger.info(f"[MASTER_DB] list_user_api_keys({user_id}) returning {len(result)} keys")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in list_user_api_keys({user_id}): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise

    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users in the master database."""
        logger.info("[MASTER_DB] list_users() called")
        try:
            await self._ensure_initialized()
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM users ORDER BY id ASC")
                rows = await cursor.fetchall()
                result = [dict(row) for row in rows]
                logger.info(f"[MASTER_DB] list_users() returning {len(result)} users")
                return result
        except Exception as e:
            logger.error(f"[MASTER_DB] ERROR in list_users(): {e}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            raise

    async def get_user_count(self) -> int:
        """Get total number of users in the master database."""
        logger.info("[MASTER_DB] ========================================")
        logger.info("[MASTER_DB] get_user_count() called")
        logger.info("[MASTER_DB] ========================================")
        
        try:
            await self._ensure_initialized()
            logger.info("[MASTER_DB] Opening database connection for user count...")
            
            async with aiosqlite.connect(MASTER_DB_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                logger.info("[MASTER_DB] Connection opened, executing COUNT query...")
                
                sql = "SELECT COUNT(*) as count FROM users"
                logger.info(f"[MASTER_DB] SQL: {sql}")
                
                cursor = await conn.execute(sql)
                logger.info(f"[MASTER_DB] Query executed")
                
                row = await cursor.fetchone()
                logger.info(f"[MASTER_DB] Row fetched: {row}")
                
                if row is None:
                    logger.error("[MASTER_DB] UNEXPECTED: COUNT query returned None!")
                    return 0
                
                count = row['count']
                logger.info(f"[MASTER_DB] User count = {count}")
                logger.info(f"[MASTER_DB] get_user_count() returning {count}")
                return count
                
        except Exception as e:
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            logger.error("[MASTER_DB] FATAL ERROR in get_user_count()")
            logger.error(f"[MASTER_DB] Exception type: {type(e).__name__}")
            logger.error(f"[MASTER_DB] Exception message: {str(e)}")
            logger.error(f"[MASTER_DB] Traceback:\n{traceback.format_exc()}")
            logger.error("[MASTER_DB] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            raise


# Global instance
_master_db: Optional[MasterDB] = None


async def get_master_db() -> MasterDB:
    """Get or create master database singleton."""
    global _master_db
    logger.info("[MASTER_DB] get_master_db() called")
    logger.info(f"[MASTER_DB] Current _master_db = {_master_db}")
    
    if _master_db is None:
        logger.info("[MASTER_DB] _master_db is None, creating new MasterDB instance...")
        _master_db = MasterDB()
        logger.info(f"[MASTER_DB] Created new MasterDB instance: {_master_db}")
    else:
        logger.info("[MASTER_DB] Returning existing MasterDB instance")
    
    return _master_db

