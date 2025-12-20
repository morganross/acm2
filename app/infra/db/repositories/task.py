"""
Task repository for CRUD operations on tasks.
"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models.task import Task, TaskStatus
from app.infra.db.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for Task CRUD operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
    
    async def get_by_run(self, run_id: str) -> Sequence[Task]:
        """Get all tasks for a specific run."""
        stmt = (
            select(Task)
            .where(Task.run_id == run_id)
            .order_by(Task.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_with_artifacts(self, id: str) -> Optional[Task]:
        """Get a task with its artifacts eagerly loaded."""
        stmt = (
            select(Task)
            .options(selectinload(Task.artifacts))
            .where(Task.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_pending_for_run(self, run_id: str) -> Sequence[Task]:
        """Get all pending tasks for a run."""
        stmt = (
            select(Task)
            .where(Task.run_id == run_id)
            .where(Task.status == TaskStatus.PENDING.value)
            .order_by(Task.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def start(self, id: str) -> Optional[Task]:
        """Mark a task as started."""
        task = await self.get_by_id(id)
        if task and task.status == TaskStatus.PENDING.value:
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(task)
            return task
        return None
    
    async def complete(
        self, 
        id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: Optional[float] = None
    ) -> Optional[Task]:
        """Mark a task as completed with token usage."""
        task = await self.get_by_id(id)
        if task:
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.utcnow()
            task.progress = 100
            task.input_tokens = input_tokens
            task.output_tokens = output_tokens
            if cost_usd is not None:
                task.cost_usd = cost_usd
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
            await self.session.commit()
            await self.session.refresh(task)
            return task
        return None
    
    async def fail(self, id: str, error_message: str) -> Optional[Task]:
        """Mark a task as failed."""
        task = await self.get_by_id(id)
        if task:
            task.status = TaskStatus.FAILED.value
            task.completed_at = datetime.utcnow()
            task.error_message = error_message
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
            await self.session.commit()
            await self.session.refresh(task)
            return task
        return None
    
    async def cancel(self, id: str) -> Optional[Task]:
        """Cancel a task."""
        task = await self.get_by_id(id)
        if task and task.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
            task.status = TaskStatus.CANCELLED.value
            task.completed_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(task)
            return task
        return None
    
    async def update_progress(self, id: str, progress: int) -> Optional[Task]:
        """Update the progress percentage of a task."""
        task = await self.get_by_id(id)
        if task:
            task.progress = max(0, min(100, progress))
            await self.session.commit()
            await self.session.refresh(task)
            return task
        return None
    
    async def count_by_status(self, run_id: str, status: TaskStatus) -> int:
        """Count tasks with a specific status for a run."""
        from sqlalchemy import func
        stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.run_id == run_id)
            .where(Task.status == status.value)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
    
    async def get_total_cost(self, run_id: str) -> float:
        """Get total cost of all tasks for a run."""
        from sqlalchemy import func
        stmt = (
            select(func.coalesce(func.sum(Task.cost_usd), 0.0))
            .where(Task.run_id == run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
