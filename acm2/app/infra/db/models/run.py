"""
Run SQLAlchemy model.

A Run is an execution of a preset - the actual evaluation job.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base

if TYPE_CHECKING:
    from app.infra.db.models.preset import Preset
    from app.infra.db.models.task import Task


def generate_id() -> str:
    return str(uuid.uuid4())


class RunStatus(str, Enum):
    """Status of a run."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(Base):
    """
    An execution run of a preset.
    
    Tracks the overall status and progress of an evaluation job.
    """
    
    __tablename__ = "runs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # Multi-tenancy: owner user ID
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None, onupdate=datetime.utcnow)
    
    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Link to preset (optional - can run without saved preset)
    preset_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("presets.id"), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING.value)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Configuration snapshot (copied from preset at run time)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Progress tracking
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    failed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    current_task: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Cost tracking
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Results summary (populated after completion)
    results_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    preset: Mapped[Optional["Preset"]] = relationship("Preset", back_populates="runs")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="run", cascade="all, delete-orphan")
    
    @property
    def progress(self) -> int:
        """Calculate progress percentage."""
        if self.total_tasks == 0:
            return 0
        return int((self.completed_tasks / self.total_tasks) * 100)
    
    def __repr__(self) -> str:
        return f"<Run(id={self.id}, title={self.title}, status={self.status})>"
    
    @property
    def progress_percent(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100


# Import here to avoid circular imports
from app.infra.db.models.artifact import Artifact  # noqa: E402, F401
