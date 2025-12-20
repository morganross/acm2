"""
Run repository for CRUD operations on runs.
"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models.run import Run, RunStatus
from app.infra.db.repositories.base import BaseRepository


class RunRepository(BaseRepository[Run]):
    """Repository for Run CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Run, session)
    
    async def get_by_preset(self, preset_id: str, limit: int = 100) -> Sequence[Run]:
        """Get all runs for a specific preset."""
        stmt = (
            select(Run)
            .where(Run.preset_id == preset_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_with_tasks(self, id: str) -> Optional[Run]:
        """Get a run with its tasks eagerly loaded."""
        stmt = (
            select(Run)
            .options(selectinload(Run.tasks))
            .where(Run.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_with_tasks(
        self, 
        limit: int = 100, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> Sequence[Run]:
        """Get all runs with tasks eagerly loaded."""
        stmt = select(Run).options(selectinload(Run.tasks))
        
        # Apply filter first
        if status:
            stmt = stmt.where(Run.status == status)
        
        # Then order, offset, limit
        stmt = stmt.order_by(Run.created_at.desc()).offset(offset).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_active_runs(self) -> Sequence[Run]:
        """Get all runs that are currently in progress."""
        stmt = (
            select(Run)
            .where(Run.status.in_([RunStatus.PENDING.value, RunStatus.RUNNING.value]))
            .order_by(Run.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def start(self, id: str) -> Optional[Run]:
        """Mark a run as started."""
        run = await self.get_by_id(id)
        if run and run.status == RunStatus.PENDING.value:
            run.status = RunStatus.RUNNING.value
            run.started_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def complete(
        self, 
        id: str, 
        results_summary: Optional[dict] = None,
        total_cost_usd: Optional[float] = None
    ) -> Optional[Run]:
        """Mark a run as completed.
        
        Preserves any existing timeline_events that were added progressively
        during execution, merging them with any new timeline_events in
        results_summary.
        """
        run = await self.get_by_id(id)
        if run:
            run.status = RunStatus.COMPLETED.value
            run.completed_at = datetime.utcnow()
            run.completed_tasks = run.total_tasks  # All done
            if results_summary:
                # Preserve existing timeline_events that were added progressively
                existing_timeline = []
                if run.results_summary and "timeline_events" in run.results_summary:
                    existing_timeline = run.results_summary["timeline_events"]
                
                # If new results_summary has timeline_events, we DON'T add them
                # because the progressive events are the source of truth now.
                # We just keep the progressive events.
                new_summary = dict(results_summary)
                new_summary["timeline_events"] = existing_timeline
                
                run.results_summary = new_summary
            if total_cost_usd is not None:
                run.total_cost_usd = total_cost_usd
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def fail(self, id: str, error_message: Optional[str] = None) -> Optional[Run]:
        """Mark a run as failed."""
        run = await self.get_by_id(id)
        if run:
            run.status = RunStatus.FAILED.value
            run.completed_at = datetime.utcnow()
            if error_message:
                run.error_message = error_message
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def cancel(self, id: str) -> Optional[Run]:
        """Cancel a run."""
        run = await self.get_by_id(id)
        if run and run.status in [RunStatus.PENDING.value, RunStatus.RUNNING.value, RunStatus.PAUSED.value]:
            run.status = RunStatus.CANCELLED.value
            run.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def pause(self, id: str) -> Optional[Run]:
        """Pause a running run."""
        run = await self.get_by_id(id)
        if run and run.status == RunStatus.RUNNING.value:
            run.status = RunStatus.PAUSED.value
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def resume(self, id: str) -> Optional[Run]:
        """Resume a paused run."""
        run = await self.get_by_id(id)
        if run and run.status == RunStatus.PAUSED.value:
            run.status = RunStatus.RUNNING.value
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def update_progress(self, id: str, completed_tasks: int, failed_tasks: int = 0) -> Optional[Run]:
        """Update the progress of a run by task counts."""
        run = await self.get_by_id(id)
        if run:
            run.completed_tasks = completed_tasks
            run.failed_tasks = failed_tasks
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def set_total_tasks(self, id: str, total: int) -> Optional[Run]:
        """Set the total number of tasks for a run."""
        run = await self.get_by_id(id)
        if run:
            run.total_tasks = total
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def increment_cost(self, id: str, cost: float, tokens: int = 0) -> Optional[Run]:
        """Add to the cumulative cost and token counts."""
        run = await self.get_by_id(id)
        if run:
            run.total_cost_usd += cost
            run.total_tokens += tokens
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
    
    async def append_timeline_event(self, id: str, event: dict) -> Optional[Run]:
        """Append a timeline event to results_summary.timeline_events.
        
        This allows progressive timeline updates during execution.
        """
        run = await self.get_by_id(id)
        if run:
            # Initialize results_summary if needed
            if run.results_summary is None:
                run.results_summary = {}
            
            # Initialize timeline_events array if needed
            if "timeline_events" not in run.results_summary:
                run.results_summary["timeline_events"] = []
            
            # Append the new event
            run.results_summary["timeline_events"].append(event)
            
            # Mark the JSON field as modified (SQLAlchemy doesn't detect in-place mutations)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(run, "results_summary")
            
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
