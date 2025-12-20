"""
Content repository for CRUD operations on content.
"""
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.content import Content, ContentType
from app.infra.db.repositories.base import BaseRepository


class ContentRepository(BaseRepository[Content]):
    """Repository for Content CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Content, session)
    
    async def get_by_type(
        self, 
        content_type: ContentType,
        limit: int = 100,
        offset: int = 0
    ) -> Sequence[Content]:
        """Get all contents of a specific type."""
        stmt = (
            select(Content)
            .where(Content.content_type == content_type.value)
            .where(Content.is_deleted == False)
            .offset(offset)
            .limit(limit)
            .order_by(Content.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_active(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> Sequence[Content]:
        """Get non-deleted contents."""
        stmt = (
            select(Content)
            .where(Content.is_deleted == False)
            .offset(offset)
            .limit(limit)
            .order_by(Content.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_by_name(self, name: str) -> Optional[Content]:
        """Get a content by its exact name."""
        stmt = (
            select(Content)
            .where(Content.name == name)
            .where(Content.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def search_by_name(
        self, 
        query: str, 
        content_type: Optional[ContentType] = None,
        limit: int = 50
    ) -> Sequence[Content]:
        """Search contents by name (case-insensitive contains)."""
        stmt = (
            select(Content)
            .where(Content.name.ilike(f"%{query}%"))
            .where(Content.is_deleted == False)
        )
        if content_type:
            stmt = stmt.where(Content.content_type == content_type.value)
        stmt = stmt.limit(limit).order_by(Content.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def search_by_tag(
        self, 
        tag: str,
        content_type: Optional[ContentType] = None,
        limit: int = 50
    ) -> Sequence[Content]:
        """Search contents by tag."""
        # Note: This is a simple approach; for complex JSON queries,
        # consider using JSON operators specific to your database
        stmt = (
            select(Content)
            .where(Content.is_deleted == False)
        )
        if content_type:
            stmt = stmt.where(Content.content_type == content_type.value)
        stmt = stmt.limit(limit).order_by(Content.name)
        result = await self.session.execute(stmt)
        # Filter by tag in Python (for SQLite compatibility)
        all_results = result.scalars().all()
        return [c for c in all_results if tag in (c.tags or [])]
    
    async def soft_delete(self, id: str) -> bool:
        """Soft delete a content."""
        content = await self.get_by_id(id)
        if content:
            content.is_deleted = True
            await self.session.commit()
            return True
        return False
    
    async def get_by_ids(self, ids: list[str]) -> Sequence[Content]:
        """Get multiple contents by their IDs."""
        if not ids:
            return []
        stmt = (
            select(Content)
            .where(Content.id.in_(ids))
            .where(Content.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update_body(
        self, 
        id: str, 
        body: str,
        variables: Optional[dict] = None
    ) -> Optional[Content]:
        """Update content body and optionally variables."""
        content = await self.get_by_id(id)
        if content:
            content.body = body
            if variables is not None:
                content.variables = variables
            await self.session.commit()
            await self.session.refresh(content)
            return content
        return None
    
    async def count_by_type(self, content_type: ContentType) -> int:
        """Count contents of a specific type."""
        stmt = (
            select(Content)
            .where(Content.content_type == content_type.value)
            .where(Content.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())
    
    async def get_input_documents(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> Sequence[Content]:
        """Get all input documents (convenience method)."""
        return await self.get_by_type(
            ContentType.INPUT_DOCUMENT, 
            limit=limit, 
            offset=offset
        )
    
    async def get_generation_instructions(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> Sequence[Content]:
        """Get all generation instructions (convenience method)."""
        return await self.get_by_type(
            ContentType.GENERATION_INSTRUCTIONS,
            limit=limit,
            offset=offset
        )
