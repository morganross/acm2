"""
User metadata model.

Stores per-user seed status, version, and profile info inside the user's SQLite DB.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class UserMeta(Base):
    """Per-user metadata for readiness gating and seeding."""

    __tablename__ = "user_meta"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, unique=True)

    # User profile info
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Seed status
    seed_status: Mapped[str] = mapped_column(String(32), nullable=False)
    seed_version: Mapped[str] = mapped_column(String(64), nullable=False)

    seeded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
