"""
GitHubConnection SQLAlchemy model.

Stores GitHub repository connection credentials for reading input files
and writing output files.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


def generate_id() -> str:
    return str(uuid.uuid4())


class GitHubConnection(Base):
    """
    Stores GitHub repository connection information.
    
    Used for:
    - Reading input documents from a GitHub repository
    - Writing generated outputs back to GitHub
    - Importing content (instructions, criteria) from GitHub
    """
    
    __tablename__ = "github_connections"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None, onupdate=datetime.utcnow)
    
    # Connection info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo: Mapped[str] = mapped_column(String(255), nullable=False)  # "owner/repo"
    branch: Mapped[str] = mapped_column(String(100), default="main")
    
    # Authentication (encrypted token)
    # NOTE: In production, use proper encryption (e.g., Fernet)
    # For now, storing as-is with a prefix to remind us it should be encrypted
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Connection status
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<GitHubConnection(id={self.id}, repo={self.repo}, branch={self.branch})>"
