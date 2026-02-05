"""
ProviderKey repository for database operations.

Handles encrypted provider API key storage with SQLAlchemy.
"""
from datetime import datetime
from typing import Dict, Optional, Sequence

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models.provider_key import ProviderKey
from app.infra.db.repositories.base import BaseRepository


class ProviderKeyRepository(BaseRepository[ProviderKey]):
    """
    Repository for managing encrypted provider API keys.
    
    Keys are stored encrypted using Fernet (AES-256). The encryption/decryption
    is handled by the caller (ProviderKeyManager), not this repository.
    
    Usage:
        repo = ProviderKeyRepository(session, user_id=user['uuid'])
        await repo.save_key("openai", encrypted_key)
        key = await repo.get_key("openai")
    """
    
    def __init__(self, session: AsyncSession, user_id: Optional[str] = None):
        super().__init__(ProviderKey, session, user_id)
    
    async def save_key(self, provider: str, encrypted_key: str) -> ProviderKey:
        """
        Save or update an encrypted provider API key.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            encrypted_key: Fernet-encrypted API key
            
        Returns:
            ProviderKey record
        """
        # Check if key already exists for this provider
        existing = await self.get_by_provider(provider)
        
        if existing:
            # Update existing key
            existing.encrypted_key = encrypted_key
            existing.updated_at = datetime.utcnow()
            existing.is_valid = True  # Reset validation status on key change
            existing.last_validated_at = None
            existing.validation_error = None
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            # Create new key
            return await self.create(
                provider=provider,
                encrypted_key=encrypted_key,
            )
    
    async def get_by_provider(self, provider: str) -> Optional[ProviderKey]:
        """
        Get provider key by provider name.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            
        Returns:
            ProviderKey or None if not found
        """
        stmt = select(ProviderKey).where(ProviderKey.provider == provider)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_key(self, provider: str) -> Optional[str]:
        """
        Get encrypted key for a provider (convenience method).
        
        Args:
            provider: Provider name
            
        Returns:
            Encrypted key string or None
        """
        record = await self.get_by_provider(provider)
        return record.encrypted_key if record else None
    
    async def get_all_keys(self) -> Dict[str, str]:
        """
        Get all provider keys as a dictionary.
        
        Returns:
            Dict mapping provider name to encrypted key
        """
        stmt = select(ProviderKey)
        stmt = self._apply_user_filter(stmt)
        result = await self.session.execute(stmt)
        records = result.scalars().all()
        return {r.provider: r.encrypted_key for r in records}
    
    async def get_all_providers(self) -> Sequence[ProviderKey]:
        """
        Get all provider key records.
        
        Returns:
            List of ProviderKey records
        """
        return await self.get_all()
    
    async def delete_key(self, provider: str) -> bool:
        """
        Delete a provider key.
        
        Args:
            provider: Provider name
            
        Returns:
            True if deleted, False if not found
        """
        record = await self.get_by_provider(provider)
        if record:
            stmt = delete(ProviderKey).where(ProviderKey.id == record.id)
            await self.session.execute(stmt)
            await self.session.commit()
            return True
        return False
    
    async def update_validation_status(
        self, 
        provider: str, 
        is_valid: bool, 
        error: Optional[str] = None
    ) -> Optional[ProviderKey]:
        """
        Update the validation status of a provider key.
        
        Args:
            provider: Provider name
            is_valid: Whether the key is valid
            error: Optional error message if invalid
            
        Returns:
            Updated ProviderKey or None if not found
        """
        record = await self.get_by_provider(provider)
        if record:
            record.is_valid = is_valid
            record.last_validated_at = datetime.utcnow()
            record.validation_error = error
            await self.session.commit()
            await self.session.refresh(record)
            return record
        return None
