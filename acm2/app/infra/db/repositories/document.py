"""
Document repository for CRUD operations on documents.
"""
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.document import Document
from app.infra.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)
    
    async def get_by_path(self, path: str) -> Optional[Document]:
        """Get a document by its file path."""
        stmt = select(Document).where(Document.path == path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Document]:
        """Get a document by its exact name."""
        stmt = select(Document).where(Document.name == name).where(Document.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_active(self, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        """Get non-deleted documents."""
        stmt = (
            select(Document)
            .where(Document.is_deleted == False)
            .offset(offset)
            .limit(limit)
            .order_by(Document.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_by_file_type(self, file_type: str) -> Sequence[Document]:
        """Get all documents of a specific file type."""
        stmt = (
            select(Document)
            .where(Document.file_type == file_type)
            .where(Document.is_deleted == False)
            .order_by(Document.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def search_by_name(self, query: str, limit: int = 50) -> Sequence[Document]:
        """Search documents by name (case-insensitive contains)."""
        stmt = (
            select(Document)
            .where(Document.name.ilike(f"%{query}%"))
            .where(Document.is_deleted == False)
            .limit(limit)
            .order_by(Document.name)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def soft_delete(self, id: str) -> bool:
        """Soft delete a document."""
        doc = await self.get_by_id(id)
        if doc:
            doc.is_deleted = True
            await self.session.commit()
            return True
        return False
    
    async def get_by_ids(self, ids: list[str]) -> Sequence[Document]:
        """Get multiple documents by their IDs."""
        if not ids:
            return []
        stmt = select(Document).where(Document.id.in_(ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update_content(
        self, 
        id: str, 
        content: str,
        content_hash: str,
        size_bytes: int,
        word_count: int
    ) -> Optional[Document]:
        """Update document content and metadata."""
        doc = await self.get_by_id(id)
        if doc:
            doc.content = content
            doc.content_hash = content_hash
            doc.size_bytes = size_bytes
            doc.word_count = word_count
            await self.session.commit()
            await self.session.refresh(doc)
            return doc
        return None
