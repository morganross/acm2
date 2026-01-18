"""
UsageStats repository for database operations.

Handles API usage tracking with SQLAlchemy.
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.usage_stats import UsageStats
from app.infra.db.repositories.base import BaseRepository


class UsageStatsRepository(BaseRepository[UsageStats]):
    """
    Repository for tracking API usage statistics.
    
    Tracks usage per user, per provider, per model, per day for:
    - Token counts (prompt, completion, total)
    - Cost tracking
    - Run counts
    
    Usage:
        repo = UsageStatsRepository(session, user_id=user['id'])
        await repo.record_usage(date.today(), "openai", "gpt-4", tokens=1000, cost=0.03)
        stats = await repo.get_stats_by_date_range(start_date, end_date)
    """
    
    def __init__(self, session: AsyncSession, user_id: Optional[int] = None):
        super().__init__(UsageStats, session, user_id)
    
    async def record_usage(
        self,
        usage_date: date,
        provider: str,
        model_id: str,
        tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
    ) -> UsageStats:
        """
        Record or update usage statistics for a provider/model/date combination.
        
        If a record already exists for the date/provider/model, increments the counts.
        Otherwise creates a new record.
        
        Args:
            usage_date: Date of the usage
            provider: Provider name (e.g., 'openai', 'anthropic')
            model_id: Model identifier (e.g., 'gpt-4', 'claude-3-opus')
            tokens: Total tokens used
            prompt_tokens: Prompt tokens used
            completion_tokens: Completion tokens used
            cost: Cost in USD
            
        Returns:
            Updated or created UsageStats record
        """
        # Look for existing record
        existing = await self.get_by_date_provider_model(usage_date, provider, model_id)
        
        if existing:
            # Increment existing record
            existing.total_tokens += tokens
            existing.prompt_tokens += prompt_tokens
            existing.completion_tokens += completion_tokens
            existing.total_cost += cost
            existing.run_count += 1
            existing.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            # Create new record
            return await self.create(
                date=usage_date,
                provider=provider,
                model_id=model_id,
                total_tokens=tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost=cost,
                run_count=1,
            )
    
    async def get_by_date_provider_model(
        self, 
        usage_date: date, 
        provider: str, 
        model_id: str
    ) -> Optional[UsageStats]:
        """
        Get usage stats for a specific date/provider/model combination.
        
        Args:
            usage_date: Date to query
            provider: Provider name
            model_id: Model identifier
            
        Returns:
            UsageStats or None
        """
        stmt = select(UsageStats).where(
            and_(
                UsageStats.date == usage_date,
                UsageStats.provider == provider,
                UsageStats.model_id == model_id,
            )
        )
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_stats_by_date_range(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Sequence[UsageStats]:
        """
        Get usage statistics for a date range.
        
        Args:
            start_date: Start date (inclusive), or None for no lower bound
            end_date: End date (inclusive), or None for no upper bound
            
        Returns:
            List of UsageStats records ordered by date descending
        """
        stmt = select(UsageStats)
        stmt = self._apply_user_filter(stmt)
        
        if start_date:
            stmt = stmt.where(UsageStats.date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStats.date <= end_date)
        
        stmt = stmt.order_by(UsageStats.date.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_stats_by_provider(
        self, 
        provider: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Sequence[UsageStats]:
        """
        Get usage statistics for a specific provider.
        
        Args:
            provider: Provider name
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of UsageStats records
        """
        stmt = select(UsageStats).where(UsageStats.provider == provider)
        stmt = self._apply_user_filter(stmt)
        
        if start_date:
            stmt = stmt.where(UsageStats.date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStats.date <= end_date)
        
        stmt = stmt.order_by(UsageStats.date.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_total_cost(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> float:
        """
        Get total cost for a date range.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Total cost in USD
        """
        stmt = select(func.sum(UsageStats.total_cost))
        stmt = self._apply_user_filter(stmt)
        
        if start_date:
            stmt = stmt.where(UsageStats.date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStats.date <= end_date)
        
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total or 0.0
    
    async def get_summary_by_provider(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Dict]:
        """
        Get usage summary grouped by provider.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with provider as key and summary stats as value
        """
        stmt = select(
            UsageStats.provider,
            func.sum(UsageStats.total_tokens).label("total_tokens"),
            func.sum(UsageStats.total_cost).label("total_cost"),
            func.sum(UsageStats.run_count).label("run_count"),
        ).group_by(UsageStats.provider)
        
        stmt = self._apply_user_filter(stmt)
        
        if start_date:
            stmt = stmt.where(UsageStats.date >= start_date)
        if end_date:
            stmt = stmt.where(UsageStats.date <= end_date)
        
        result = await self.session.execute(stmt)
        rows = result.all()
        
        return {
            row.provider: {
                "total_tokens": row.total_tokens or 0,
                "total_cost": row.total_cost or 0.0,
                "run_count": row.run_count or 0,
            }
            for row in rows
        }
