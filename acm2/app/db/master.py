"""
Master Database Manager (MySQL)
Handles user accounts and API keys
"""
import aiomysql
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class MasterDB:
    """Manages master database with user accounts and API keys."""
    
    def __init__(self, host: str = 'localhost', user: str = 'root', 
                 password: str = '', db: str = 'acm2_master'):
        """Initialize master database connection pool.
        
        Args:
            host: MySQL host
            user: MySQL username
            password: MySQL password
            db: Database name
        """
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'db': db,
            'charset': 'utf8mb4',
            'autocommit': True
        }
        self._pool: Optional[aiomysql.Pool] = None
    
    async def connect(self):
        """Create connection pool."""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                **self.config,
                minsize=1,
                maxsize=5,
                pool_recycle=3600  # Recycle connections after 1 hour
            )
            logger.info("Master database pool created (minsize=1, maxsize=5)")
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("Master database pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            yield conn
    
    async def create_user(self, username: str, email: str,
                         wordpress_user_id: Optional[int] = None) -> int:
        """Create a new user.
        
        Args:
            username: Unique username
            email: User email address
            wordpress_user_id: Optional WordPress user ID
            
        Returns:
            New user's ID
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO users (username, email, wordpress_user_id)
                       VALUES (%s, %s, %s)""",
                    (username, email, wordpress_user_id)
                )
                user_id = cursor.lastrowid
                logger.info(f"Created user: {username} (ID: {user_id})")
                return user_id
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM users WHERE id = %s", (user_id,)
                )
                return await cursor.fetchone()
    
    async def get_user_by_wordpress_id(self, wordpress_id: int) -> Optional[Dict[str, Any]]:
        """Get user by WordPress user ID."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM users WHERE wordpress_user_id = %s",
                    (wordpress_id,)
                )
                return await cursor.fetchone()
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email address."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM users WHERE email = %s", (email,)
                )
                return await cursor.fetchone()
    
    async def create_api_key(self, user_id: int, key_hash: str,
                           key_prefix: str, name: Optional[str] = None) -> int:
        """Store API key for user.
        
        Args:
            user_id: User ID
            key_hash: bcrypt hash of the API key
            key_prefix: First 8 chars for display
            name: Optional name for the key
            
        Returns:
            API key record ID
        """
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO api_keys (user_id, key_hash, key_prefix, name)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, key_hash, key_prefix, name)
                )
                key_id = cursor.lastrowid
                logger.info(f"Created API key for user {user_id}: {key_prefix}...")
                return key_id
    
    async def get_user_by_api_key_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user by API key hash.
        
        Args:
            key_hash: bcrypt hash of API key
            
        Returns:
            User dict or None if key not found/revoked
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get user and update last_used_at
                await cursor.execute(
                    """SELECT u.* FROM users u
                       JOIN api_keys k ON u.id = k.user_id
                       WHERE k.key_hash = %s AND k.revoked_at IS NULL""",
                    (key_hash,)
                )
                user = await cursor.fetchone()
                
                if user:
                    # Update last_used_at
                    await cursor.execute(
                        "UPDATE api_keys SET last_used_at = %s WHERE key_hash = %s",
                        (datetime.utcnow(), key_hash)
                    )
                
                return user
    
    async def revoke_api_key(self, key_id: int):
        """Revoke an API key."""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE api_keys SET revoked_at = %s WHERE id = %s",
                    (datetime.utcnow(), key_id)
                )
                logger.info(f"Revoked API key ID: {key_id}")
    
    async def list_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """List all API keys for a user."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """SELECT id, key_prefix, name, created_at, last_used_at, 
                              revoked_at
                       FROM api_keys
                       WHERE user_id = %s
                       ORDER BY created_at DESC""",
                    (user_id,)
                )
                return await cursor.fetchall()

    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users in the master database."""
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM users ORDER BY id ASC")
                return await cursor.fetchall()


# Global instance
_master_db: Optional[MasterDB] = None


async def get_master_db() -> MasterDB:
    """Get or create master database singleton."""
    global _master_db
    if _master_db is None:
        _master_db = MasterDB()
        await _master_db.connect()
    return _master_db

