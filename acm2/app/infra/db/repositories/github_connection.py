"""
GitHubConnection repository for CRUD operations on GitHub connections.
"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.github_connection import GitHubConnection
from app.infra.db.repositories.base import BaseRepository


class GitHubConnectionRepository(BaseRepository[GitHubConnection]):
    """Repository for GitHubConnection CRUD operations."""
    
    def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
        super().__init__(GitHubConnection, session, user_id)
    
    async def get_active(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> Sequence[GitHubConnection]:
        """Get non-deleted connections (scoped to user if user_id is set)."""
        stmt = (
            select(GitHubConnection)
            .where(GitHubConnection.is_deleted == False)
            .offset(offset)
            .limit(limit)
            .order_by(GitHubConnection.name)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_by_repo(self, repo: str) -> Optional[GitHubConnection]:
        """Get a connection by repository name (owner/repo) (scoped to user if user_id is set)."""
        stmt = (
            select(GitHubConnection)
            .where(GitHubConnection.repo == repo)
            .where(GitHubConnection.is_deleted == False)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[GitHubConnection]:
        """Get a connection by its display name (scoped to user if user_id is set)."""
        stmt = (
            select(GitHubConnection)
            .where(GitHubConnection.name == name)
            .where(GitHubConnection.is_deleted == False)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_valid_connections(self) -> Sequence[GitHubConnection]:
        """Get all connections that have been verified as valid (scoped to user if user_id is set)."""
        stmt = (
            select(GitHubConnection)
            .where(GitHubConnection.is_valid == True)
            .where(GitHubConnection.is_deleted == False)
            .order_by(GitHubConnection.name)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update_test_status(
        self, 
        id: str, 
        is_valid: bool,
        error: Optional[str] = None
    ) -> Optional[GitHubConnection]:
        """Update the test status of a connection."""
        connection = await self.get_by_id(id)
        if connection:
            connection.is_valid = is_valid
            connection.last_tested_at = datetime.utcnow()
            connection.last_error = error
            await self.session.commit()
            await self.session.refresh(connection)
            return connection
        return None
    
    async def soft_delete(self, id: str) -> bool:
        """Soft delete a connection."""
        connection = await self.get_by_id(id)
        if connection:
            connection.is_deleted = True
            await self.session.commit()
            return True
        return False
    
    async def update_token(
        self, 
        id: str, 
        token_encrypted: str
    ) -> Optional[GitHubConnection]:
        """Update the encrypted token for a connection."""
        connection = await self.get_by_id(id)
        if connection:
            connection.token_encrypted = token_encrypted
            # Reset validation status when token changes
            connection.is_valid = True
            connection.last_tested_at = None
            connection.last_error = None
            await self.session.commit()
            await self.session.refresh(connection)
            return connection
        return None
