"""
Provider Key Manager

Manages encrypted LLM provider API keys for users.
"""
from typing import Optional, Dict
import logging

from acm2.app.db.user_db import get_user_db
from acm2.app.security.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class ProviderKeyManager:
    """Manages provider API keys for a user."""
    
    SUPPORTED_PROVIDERS = ['openai', 'anthropic', 'google']
    
    def __init__(self, user_id: int):
        """Initialize provider key manager.
        
        Args:
            user_id: User ID from master database
        """
        self.user_id = user_id
        self.encryption_service = get_encryption_service()
    
    async def save_key(self, provider: str, api_key: str):
        """Save (encrypt and store) a provider API key.
        
        Args:
            provider: Provider name ('openai', 'anthropic', 'google')
            api_key: Plain text API key
            
        Raises:
            ValueError: If provider not supported
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )
        
        # Encrypt the key
        encrypted_key = self.encryption_service.encrypt(api_key)
        
        # Store in user's database
        user_db = await get_user_db(self.user_id)
        await user_db.save_provider_key(provider, encrypted_key)
        
        logger.info(f"Saved {provider} key for user {self.user_id}")
    
    async def get_key(self, provider: str) -> Optional[str]:
        """Get (retrieve and decrypt) a provider API key.
        
        Args:
            provider: Provider name
            
        Returns:
            Plain text API key or None if not found
        """
        user_db = await get_user_db(self.user_id)
        encrypted_key = await user_db.get_provider_key(provider)
        
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
        """Get all provider keys for user.
        
        Returns:
            Dict mapping provider name to decrypted API key
        """
        user_db = await get_user_db(self.user_id)
        encrypted_keys = await user_db.get_all_provider_keys()
        
        decrypted_keys = {}
        for provider, encrypted_key in encrypted_keys.items():
            try:
                decrypted_keys[provider] = self.encryption_service.decrypt(encrypted_key)
            except Exception as e:
                logger.error(f"Failed to decrypt {provider} key: {e}")
        
        return decrypted_keys
    
    async def delete_key(self, provider: str):
        """Delete a provider API key.
        
        Args:
            provider: Provider name
        """
        user_db = await get_user_db(self.user_id)
        await user_db.delete_provider_key(provider)
        logger.info(f"Deleted {provider} key for user {self.user_id}")
    
    async def has_key(self, provider: str) -> bool:
        """Check if user has a key for provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if key exists
        """
        key = await self.get_key(provider)
        return key is not None
    
    async def list_configured_providers(self) -> list:
        """List all providers that have keys configured.
        
        Returns:
            List of provider names
        """
        keys = await self.get_all_keys()
        return list(keys.keys())


async def get_provider_key_manager(user_id: int) -> ProviderKeyManager:
    """Get provider key manager for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        ProviderKeyManager instance
    """
    return ProviderKeyManager(user_id)
