"""
ProviderKey SQLAlchemy model.

Stores encrypted API keys for AI providers (OpenAI, Anthropic, Google, etc.)
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


def generate_id() -> str:
    return str(uuid.uuid4())


class ProviderKey(Base):
    """
    Stores encrypted provider API keys.
    
    Each user has their own set of provider keys stored in their
    per-user SQLite database. Keys are encrypted at rest using
    Fernet (AES-256) encryption.
    
    Supported providers:
    - openai
    - anthropic
    - google
    - openrouter
    - groq
    """
    
    __tablename__ = "provider_keys"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_uuid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)  # Multi-tenancy: owner user UUID
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None, onupdate=datetime.utcnow)
    
    # Provider name - unique per user (enforced by repository logic, not DB constraint
    # since per-user DBs mean each user has their own table)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Encrypted API key (Fernet/AES-256 encrypted)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional metadata
    is_valid: Mapped[bool] = mapped_column(default=True)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    validation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    def __repr__(self) -> str:
        return f"<ProviderKey(id={self.id}, provider={self.provider}, user_uuid={self.user_uuid})>"
