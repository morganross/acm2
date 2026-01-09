"""
Per-User Database Manager (SQLite)

Each user has their own SQLite database file for complete isolation.
"""
import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class UserDB:
    """Manages a single user's database."""
    
    def __init__(self, user_id: int, data_dir: str = "data"):
        """Initialize user database.
        
        Args:
            user_id: User ID from master database
            data_dir: Directory for user database files
        """
        self.user_id = user_id
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / f"user_{user_id}.db"
        self._conn: Optional[aiosqlite.Connection] = None
    
    async def init_db(self):
        """Initialize user database with schema."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        schema_path = Path(__file__).parent / "user_schema.sql"
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()
        
        logger.info(f"User database initialized: {self.db_path}")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection (creates if needed)."""
        if not self.db_path.exists():
            await self.init_db()
        
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
    async def create_run(self, run_id: str, name: str, **kwargs) -> str:
        """Create a new evaluation run.
        
        Args:
            run_id: Unique run ID
            name: Run name
            **kwargs: Additional run fields (system_prompt, user_prompt, etc.)
            
        Returns:
            Run ID
        """
        async with self.get_connection() as conn:
            fields = ['id', 'name', 'status']
            values = [run_id, name, kwargs.get('status', 'pending')]
            
            # Add optional fields
            for field in ['system_prompt', 'user_prompt', 'model_ids', 'criteria']:
                if field in kwargs:
                    fields.append(field)
                    values.append(kwargs[field])
            
            placeholders = ','.join(['?' for _ in values])
            await conn.execute(
                f"INSERT INTO runs ({','.join(fields)}) VALUES ({placeholders})",
                values
            )
            await conn.commit()
            logger.info(f"Created run {run_id} for user {self.user_id}")
            return run_id
    
    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM runs WHERE id = ?", (run_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_run(self, run_id: str, **kwargs):
        """Update run fields."""
        if not kwargs:
            return
        
        async with self.get_connection() as conn:
            set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [run_id]
            
            await conn.execute(
                f"UPDATE runs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            await conn.commit()
            logger.info(f"Updated run {run_id} for user {self.user_id}")
    
    async def list_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List user's runs."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM runs 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def save_provider_key(self, provider: str, encrypted_key: str):
        """Save encrypted provider API key.
        
        Args:
            provider: Provider name ('openai', 'anthropic', 'google')
            encrypted_key: AES-256 encrypted key
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO provider_keys 
                   (provider, encrypted_key, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)""",
                (provider, encrypted_key)
            )
            await conn.commit()
            logger.info(f"Saved {provider} key for user {self.user_id}")
    
    async def get_provider_key(self, provider: str) -> Optional[str]:
        """Get encrypted provider key."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT encrypted_key FROM provider_keys WHERE provider = ?",
                (provider,)
            )
            row = await cursor.fetchone()
            return row['encrypted_key'] if row else None
    
    async def get_all_provider_keys(self) -> Dict[str, str]:
        """Get all provider keys as dict."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT provider, encrypted_key FROM provider_keys"
            )
            rows = await cursor.fetchall()
            return {row['provider']: row['encrypted_key'] for row in rows}
    
    async def delete_provider_key(self, provider: str):
        """Delete provider key."""
        async with self.get_connection() as conn:
            await conn.execute(
                "DELETE FROM provider_keys WHERE provider = ?", (provider,)
            )
            await conn.commit()
            logger.info(f"Deleted {provider} key for user {self.user_id}")
    
    async def record_usage(self, date: str, provider: str, model_id: str,
                          tokens: int, cost: float):
        """Record usage statistics.
        
        Args:
            date: Date in YYYY-MM-DD format
            provider: Provider name
            model_id: Model identifier
            tokens: Token count
            cost: Cost in USD
        """
        async with self.get_connection() as conn:
            await conn.execute(
                """INSERT INTO usage_stats 
                   (date, provider, model_id, total_tokens, total_cost, run_count)
                   VALUES (?, ?, ?, ?, ?, 1)
                   ON CONFLICT(date, provider, model_id) DO UPDATE SET
                   total_tokens = total_tokens + excluded.total_tokens,
                   total_cost = total_cost + excluded.total_cost,
                   run_count = run_count + 1""",
                (date, provider, model_id, tokens, cost)
            )
            await conn.commit()
    
    async def get_usage_stats(self, start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get usage statistics for date range."""
        async with self.get_connection() as conn:
            query = "SELECT * FROM usage_stats WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date DESC"
            
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_user_db(user_id: int) -> UserDB:
    """Get or create user database instance.
    
    Args:
        user_id: User ID from master database
        
    Returns:
        UserDB instance
    """
    user_db = UserDB(user_id)
    # Ensure database exists
    if not user_db.db_path.exists():
        await user_db.init_db()
    return user_db
