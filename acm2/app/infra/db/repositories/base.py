"""
Base repository class with common CRUD operations.
"""
from typing import Generic, TypeVar, Type, Optional, Sequence
from uuid import uuid4

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import Base

# Type variable for model classes
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.
    
    Inherit from this class and specify the model type:
        class PresetRepository(BaseRepository[Preset]):
            def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
                super().__init__(Preset, session, user_id)
    
    When user_id is provided, all queries will be scoped to that user's data.
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession, user_id: Optional[int] = None):
        self.model = model
        self.session = session
        self.user_id = user_id
    
    def _apply_user_filter(self, stmt):
        """Apply user_id filter if set and model has user_id column."""
        if self.user_id is not None and hasattr(self.model, 'user_id'):
            return stmt.where(self.model.user_id == self.user_id)
        return stmt
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        
        # Automatically set user_id if repository is scoped to a user
        if self.user_id is not None and hasattr(self.model, 'user_id') and 'user_id' not in kwargs:
            kwargs['user_id'] = self.user_id
        
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """Get a record by ID (scoped to user if user_id is set)."""
        stmt = select(self.model).where(self.model.id == id)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> Sequence[ModelType]:
        """Get all records with pagination (scoped to user if user_id is set)."""
        stmt = select(self.model).offset(offset).limit(limit)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """Update a record by ID (scoped to user if user_id is set)."""
        # First verify the record belongs to this user
        existing = await self.get_by_id(id)
        if existing is None:
            return None
        
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        if self.user_id is not None and hasattr(self.model, 'user_id'):
            stmt = stmt.where(self.model.user_id == self.user_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()
    
    async def delete(self, id: str) -> bool:
        """Delete a record by ID (scoped to user if user_id is set). Returns True if deleted."""
        stmt = delete(self.model).where(self.model.id == id)
        if self.user_id is not None and hasattr(self.model, 'user_id'):
            stmt = stmt.where(self.model.user_id == self.user_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def exists(self, id: str) -> bool:
        """Check if a record exists (scoped to user if user_id is set)."""
        stmt = select(self.model.id).where(self.model.id == id)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def count(self) -> int:
        """Count all records (scoped to user if user_id is set)."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.model)
        if self.user_id is not None and hasattr(self.model, 'user_id'):
            stmt = stmt.where(self.model.user_id == self.user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
