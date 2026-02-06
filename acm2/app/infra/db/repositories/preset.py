"""
Preset repository for CRUD operations on presets.
"""
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models.preset import Preset
from app.infra.db.repositories.base import BaseRepository


class PresetRepository(BaseRepository[Preset]):
    """Repository for Preset CRUD operations."""
    
    def __init__(self, session: AsyncSession, user_uuid: Optional[str] = None):
        super().__init__(Preset, session, user_uuid)
    
    async def get_by_name(self, name: str) -> Optional[Preset]:
        """Get a preset by name (scoped to user if user_uuid is set)."""
        stmt = select(Preset).where(Preset.name == name)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_active(self, limit: int = 100, offset: int = 0) -> Sequence[Preset]:
        """Get all presets with runs eagerly loaded (scoped to user if user_uuid is set)."""
        stmt = (
            select(Preset)
            .options(selectinload(Preset.runs))
            .offset(offset)
            .limit(limit)
            .order_by(Preset.created_at.desc())
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_by_id(self, id: str) -> Optional[Preset]:
        """Get a preset by ID with runs eagerly loaded (scoped to user if user_uuid is set)."""
        stmt = (
            select(Preset)
            .options(selectinload(Preset.runs))
            .where(Preset.id == id)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> Preset:
        """Create a new preset and ensure runs is initialized."""
        preset = await super().create(**kwargs)
        # For a new preset, runs is empty. We set it explicitly to avoid lazy load errors
        # when accessing it later in the response model.
        # We use the internal __dict__ or set_committed_value to avoid triggering loading
        from sqlalchemy.orm import attributes
        attributes.set_committed_value(preset, "runs", [])
        return preset

    async def get_by_id_with_runs(self, id: str) -> Optional[Preset]:
        """Get a preset by ID with runs eagerly loaded (scoped to user if user_uuid is set)."""
        stmt = (
            select(Preset)
            .options(selectinload(Preset.runs))
            .where(Preset.id == id)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def delete(self, id: str) -> bool:
        """Permanently delete a preset from the database."""
        preset = await self.get_by_id(id)
        if preset:
            await self.session.delete(preset)
            await self.session.commit()
            return True
        return False
    
    async def duplicate(self, id: str, new_name: str) -> Optional[Preset]:
        """Create a copy of an existing preset with a new name."""
        original = await self.get_by_id(id)
        if not original:
            return None
        
        return await self.create(
            name=new_name,
            description=original.description,
            documents=original.documents,
            models=original.models,
            generators=original.generators,
            evaluation_enabled=original.evaluation_enabled,
            pairwise_enabled=original.pairwise_enabled,
            gptr_config=original.gptr_config,
            fpf_config=original.fpf_config,
            config_overrides=original.config_overrides,
        )
