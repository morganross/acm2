"""
Run repository for CRUD operations on runs.
"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infra.db.models.run import Run, RunStatus
from app.infra.db.repositories.base import BaseRepository


class RunRepository(BaseRepository[Run]):
    """Repository for Run CRUD operations."""
    
    def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
        super().__init__(Run, session, user_id)
    
    async def get_by_preset(self, preset_id: str, limit: int = 100) -> Sequence[Run]:
        """Get all runs for a specific preset (scoped to user if user_id is set)."""
        stmt = (
            select(Run)
            .where(Run.preset_id == preset_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_with_tasks(self, id: str) -> Optional[Run]:
        """Get a run with its tasks eagerly loaded (scoped to user if user_id is set)."""
        stmt = (
            select(Run)
            .options(selectinload(Run.tasks))
            .where(Run.id == id)
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_with_tasks(
        self, 
        limit: int = 100, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> Sequence[Run]:
        """Get all runs with tasks eagerly loaded (scoped to user if user_id is set)."""
        stmt = select(Run).options(selectinload(Run.tasks))
        
        # Apply user filter
        stmt = self._apply_user_filter(stmt)
        
        # Apply status filter
        if status:
            stmt = stmt.where(Run.status == status)
        
        # Then order, offset, limit
        stmt = stmt.order_by(Run.created_at.desc()).offset(offset).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def count(self, status: Optional[str] = None) -> int:
        """Return the total number of runs (optionally filtered by status, scoped to user if user_id is set)."""
        stmt = select(func.count()).select_from(Run)
        if self.user_id is not None:
            stmt = stmt.where(Run.user_id == self.user_id)
        if status:
            stmt = stmt.where(Run.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def bulk_delete_by_status(self, statuses: list[str]) -> int:
        """Delete all runs whose status is in the provided list (scoped to user if user_id is set)."""
        if not statuses:
            return 0
        stmt = delete(Run).where(Run.status.in_(statuses))
        if self.user_id is not None:
            stmt = stmt.where(Run.user_id == self.user_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0
    
    async def get_active_runs(self) -> Sequence[Run]:
        """Get all runs that are currently in progress (scoped to user if user_id is set)."""
        stmt = (
            select(Run)
            .where(Run.status.in_([RunStatus.PENDING.value, RunStatus.RUNNING.value]))
            .order_by(Run.created_at.asc())
        )
        stmt = self._apply_user_filter(stmt)
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

    async def append_generated_doc(self, id: str, doc_info: dict) -> Optional[Run]:
        """Append a generated doc to results_summary.generated_docs.
        
        This allows progressive generated_docs updates during execution without
        overwriting other fields like timeline_events.
        """
        run = await self.get_by_id(id)
        if run:
            # Initialize results_summary if needed
            if run.results_summary is None:
                run.results_summary = {}
            
            # Initialize generated_docs array if needed
            if "generated_docs" not in run.results_summary:
                run.results_summary["generated_docs"] = []
            
            # Append the new doc info
            run.results_summary["generated_docs"].append(doc_info)
            run.results_summary["generated_count"] = len(run.results_summary["generated_docs"])
            
            # Mark the JSON field as modified (SQLAlchemy doesn't detect in-place mutations)
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(run, "results_summary")
            
            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None

    async def append_source_doc_generated_doc(self, id: str, source_doc_id: str, doc_info: dict) -> Optional[Run]:
        """Append a generated doc to results_summary.source_doc_results[source_doc_id].generated_docs."""
        run = await self.get_by_id(id)
        if run:
            if run.results_summary is None:
                run.results_summary = {}

            if "source_doc_results" not in run.results_summary or not isinstance(run.results_summary.get("source_doc_results"), dict):
                run.results_summary["source_doc_results"] = {}

            sdr = run.results_summary["source_doc_results"].get(source_doc_id)
            if not isinstance(sdr, dict):
                sdr = {
                    "source_doc_id": source_doc_id,
                    "source_doc_name": source_doc_id,
                    "status": "pending",
                    "generated_docs": [],
                    "single_eval_results": {},
                    "pairwise_results": None,
                    "winner_doc_id": None,
                    "combined_doc": None,
                    "timeline_events": [],
                    "errors": [],
                    "cost_usd": 0.0,
                    "duration_seconds": 0.0,
                }

            if "generated_docs" not in sdr or not isinstance(sdr.get("generated_docs"), list):
                sdr["generated_docs"] = []

            sdr["generated_docs"].append(doc_info)
            run.results_summary["source_doc_results"][source_doc_id] = sdr

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(run, "results_summary")

            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None

    async def upsert_source_doc_single_eval_result(
        self,
        id: str,
        source_doc_id: str,
        gen_doc_id: str,
        summary: dict,
    ) -> Optional[Run]:
        """Upsert results_summary.source_doc_results[source_doc_id].single_eval_results[gen_doc_id].

        The stored value should be a dict-like summary containing at least avg_score,
        so the API layer can derive SourceDocResultResponse.single_eval_scores.
        """
        run = await self.get_by_id(id)
        if run:
            if run.results_summary is None:
                run.results_summary = {}

            if "source_doc_results" not in run.results_summary or not isinstance(run.results_summary.get("source_doc_results"), dict):
                run.results_summary["source_doc_results"] = {}

            sdr = run.results_summary["source_doc_results"].get(source_doc_id)
            if not isinstance(sdr, dict):
                sdr = {
                    "source_doc_id": source_doc_id,
                    "source_doc_name": source_doc_id,
                    "status": "pending",
                    "generated_docs": [],
                    "single_eval_results": {},
                    "pairwise_results": None,
                    "winner_doc_id": None,
                    "combined_doc": None,
                    "timeline_events": [],
                    "errors": [],
                    "cost_usd": 0.0,
                    "duration_seconds": 0.0,
                }

            if "single_eval_results" not in sdr or not isinstance(sdr.get("single_eval_results"), dict):
                sdr["single_eval_results"] = {}

            sdr["single_eval_results"][gen_doc_id] = summary
            run.results_summary["source_doc_results"][source_doc_id] = sdr

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(run, "results_summary")

            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None

    async def append_source_doc_timeline_event(self, id: str, source_doc_id: str, event: dict) -> Optional[Run]:
        """Append a timeline event to results_summary.source_doc_results[source_doc_id].timeline_events."""
        run = await self.get_by_id(id)
        if run:
            if run.results_summary is None:
                run.results_summary = {}

            if "source_doc_results" not in run.results_summary or not isinstance(run.results_summary.get("source_doc_results"), dict):
                run.results_summary["source_doc_results"] = {}

            sdr = run.results_summary["source_doc_results"].get(source_doc_id)
            if not isinstance(sdr, dict):
                sdr = {
                    "source_doc_id": source_doc_id,
                    "source_doc_name": source_doc_id,
                    "status": "pending",
                    "generated_docs": [],
                    "single_eval_results": {},
                    "pairwise_results": None,
                    "winner_doc_id": None,
                    "combined_doc": None,
                    "timeline_events": [],
                    "errors": [],
                    "cost_usd": 0.0,
                    "duration_seconds": 0.0,
                }

            if "timeline_events" not in sdr or not isinstance(sdr.get("timeline_events"), list):
                sdr["timeline_events"] = []

            sdr["timeline_events"].append(event)
            run.results_summary["source_doc_results"][source_doc_id] = sdr

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(run, "results_summary")

            await self.session.commit()
            await self.session.refresh(run)
            return run
        return None
