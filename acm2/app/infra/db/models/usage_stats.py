"""
UsageStats SQLAlchemy model.

Tracks API usage statistics for billing and monitoring.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


def generate_id() -> str:
    return str(uuid.uuid4())


class UsageStats(Base):
    """
    Tracks API usage statistics per user, per provider, per model, per day.
    
    Used for:
    - Cost tracking and budgeting
    - Usage analytics
    - Rate limit monitoring
    """
    
    __tablename__ = "usage_stats"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # Multi-tenancy: owner user ID
    
    # Date and provider/model identification
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Usage metrics
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<UsageStats(id={self.id}, date={self.date}, provider={self.provider}, model_id={self.model_id})>"
