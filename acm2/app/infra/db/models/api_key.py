"""
API Keys Model for User Database

Stores API keys in each user's individual SQLite database.
Enables master-db-free authentication with embedded user_id in key.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.infra.db.base import Base


class ApiKey(Base):
    """API key stored in user's database for authentication."""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(30), nullable=False, index=True)  # For display: "acm2_u42_kKDH..."
    name = Column(String(100), nullable=True)  # Optional key name
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<ApiKey(id={self.id}, prefix='{self.key_prefix}', active={self.is_active})>"
