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
            def __init__(self, session: AsyncSession):
                super().__init__(Preset, session)
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """Get a record by ID."""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> Sequence[ModelType]:
        """Get all records with pagination."""
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """Update a record by ID."""
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()
    
    async def delete(self, id: str) -> bool:
        """Delete a record by ID. Returns True if deleted."""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
    
    async def exists(self, id: str) -> bool:
        """Check if a record exists."""
        stmt = select(self.model.id).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def count(self) -> int:
        """Count all records."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()
