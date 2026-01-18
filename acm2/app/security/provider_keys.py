"""
Provider Key Manager

Manages encrypted LLM provider API keys for users.
Uses SQLAlchemy for database operations.
"""
from typing import Optional, Dict, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.repositories.provider_key import ProviderKeyRepository
from app.security.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class ProviderKeyManager:
    """Manages provider API keys for a user using SQLAlchemy.
    
    This class handles encryption/decryption of API keys and delegates
    storage to the ProviderKeyRepository.
    
    Usage:
        # In a route with database session
        async def my_route(db: AsyncSession = Depends(get_user_db), user: dict = Depends(get_current_user)):
            manager = ProviderKeyManager(db, user_id=user['id'])
            await manager.save_key("openai", "sk-...")
            key = await manager.get_key("openai")
    """
    
    SUPPORTED_PROVIDERS = ['openai', 'anthropic', 'google', 'openrouter', 'groq']
    
    def __init__(self, session: AsyncSession, user_id: int):
        """Initialize provider key manager.
        
        Args:
            session: SQLAlchemy async session for the user's database
            user_id: User ID from master database
        """
        self.user_id = user_id
        self.session = session
        self.encryption_service = get_encryption_service()
        self._repo = ProviderKeyRepository(session, user_id=user_id)
    
    async def save_key(self, provider: str, api_key: str):
        """Save (encrypt and store) a provider API key.
        
        Args:
            provider: Provider name ('openai', 'anthropic', 'google', etc.)
            api_key: Plain text API key
            
        Raises:
            ValueError: If provider not supported
        """
        provider = provider.lower()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )
        
        # Encrypt the key
        encrypted_key = self.encryption_service.encrypt(api_key)
        
        # Store in user's database via repository
        await self._repo.save_key(provider, encrypted_key)
        
        logger.info(f"Saved {provider} key for user {self.user_id}")
    
    async def get_key(self, provider: str) -> Optional[str]:
        """Get (retrieve and decrypt) a provider API key.
        
        Args:
            provider: Provider name
            
        Returns:
            Plain text API key or None if not found
        """
        provider = provider.lower()
        encrypted_key = await self._repo.get_key(provider)
        
        if not encrypted_key:
            return None
        
        # Decrypt the key
        try:
            decrypted_key = self.encryption_service.decrypt(encrypted_key)
            logger.debug(f"Retrieved {provider} key for user {self.user_id}")
            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt {provider} key for user {self.user_id}: {e}")
            return None
    
    async def get_all_keys(self) -> Dict[str, str]:
        """Get all provider keys for user (decrypted).
        
        Returns:
            Dict mapping provider name to decrypted API key
        """
        encrypted_keys = await self._repo.get_all_keys()
        
        decrypted_keys = {}
        for provider, encrypted_key in encrypted_keys.items():
            try:
                decrypted_keys[provider] = self.encryption_service.decrypt(encrypted_key)
            except Exception as e:
                logger.error(f"Failed to decrypt {provider} key: {e}")
        
        return decrypted_keys
    
    async def delete_key(self, provider: str) -> bool:
        """Delete a provider API key.
        
        Args:
            provider: Provider name
            
        Returns:
            True if deleted, False if not found
        """
        provider = provider.lower()
        deleted = await self._repo.delete_key(provider)
        if deleted:
            logger.info(f"Deleted {provider} key for user {self.user_id}")
        return deleted
    
    async def has_key(self, provider: str) -> bool:
        """Check if user has a key for provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if key exists
        """
        provider = provider.lower()
        key = await self._repo.get_key(provider)
        return key is not None
    
    async def list_configured_providers(self) -> List[str]:
        """List all providers that have keys configured.
        
        Returns:
            List of provider names
        """
        keys = await self._repo.get_all_keys()
        return list(keys.keys())
    
    async def validate_key(self, provider: str) -> bool:
        """Validate a provider key by attempting a simple API call.
        
        Note: This is a placeholder. Actual validation would need
        provider-specific API calls.
        
        Args:
            provider: Provider name
            
        Returns:
            True if valid
        """
        # TODO: Implement actual API validation per provider
        # For now, just check if key exists and can be decrypted
        key = await self.get_key(provider)
        is_valid = key is not None
        await self._repo.update_validation_status(provider, is_valid)
        return is_valid


def get_provider_key_manager(session: AsyncSession, user_id: int) -> ProviderKeyManager:
    """Get provider key manager for a user.
    
    Args:
        session: SQLAlchemy async session
        user_id: User ID
        
    Returns:
        ProviderKeyManager instance
    """
    return ProviderKeyManager(session, user_id)
