"""
Provider Key Injection Service

This module provides functionality to inject decrypted provider API keys
into the environment for LLM adapters. Keys are fetched from the user's
encrypted database and temporarily injected into process environment.
"""
import os
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.security.provider_keys import ProviderKeyManager


# Provider name to environment variable mapping
PROVIDER_TO_ENV_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
}


async def inject_provider_keys_for_user(
    session: AsyncSession, 
    user_id: int, 
    env: Dict[str, str]
) -> Dict[str, str]:
    """
    Fetch and inject all configured provider API keys for a user into an environment dict.
    
    Args:
        session: SQLAlchemy async session for the user's database
        user_id: The user ID to fetch keys for
        env: The environment dictionary to inject keys into (typically os.environ.copy())
    
    Returns:
        The updated environment dictionary with provider keys injected
        
    Example:
        env = os.environ.copy()
        async with get_user_db_session(user) as session:
            env = await inject_provider_keys_for_user(session, user_id=1, env=env)
        # Now env contains OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    """
    manager = ProviderKeyManager(session, user_id)
    
    # Get all configured providers (already decrypted)
    decrypted_keys = await manager.get_all_keys()
    
    # Inject each provider's key (use already-decrypted values)
    for provider, key in decrypted_keys.items():
        env_var = PROVIDER_TO_ENV_VAR.get(provider)
        if env_var and key:
            env[env_var] = key
    
    return env


async def inject_provider_keys_for_user_auto(
    user_id: int,
    env: Dict[str, str],
) -> Dict[str, str]:
    """
    Convenience function that automatically creates a database session.
    
    Use this when you don't have an existing session (e.g., in adapters).
    For routes that already have a session, use inject_provider_keys_for_user() instead.
    
    Args:
        user_id: The user ID to fetch keys for
        env: The environment dictionary to inject keys into
        
    Returns:
        The updated environment dictionary with provider keys injected
    """
    from app.infra.db.session import get_user_db_session
    
    # Create a minimal user dict for the session factory
    user = {"id": user_id}
    
    async for session in get_user_db_session(user):
        return await inject_provider_keys_for_user(session, user_id, env)
    
    return env  # Return unchanged if session creation fails


async def get_provider_key(
    session: AsyncSession, 
    user_id: int, 
    provider: str
) -> Optional[str]:
    """
    Get a single decrypted provider API key for a user.
    
    Args:
        session: SQLAlchemy async session for the user's database
        user_id: The user ID to fetch key for
        provider: The provider name (openai, anthropic, google, etc.)
    
    Returns:
        The decrypted API key or None if not configured
        
    Example:
        async with get_user_db_session(user) as session:
            openai_key = await get_provider_key(session, user_id=1, provider="openai")
            if openai_key:
                client = OpenAI(api_key=openai_key)
    """
    manager = ProviderKeyManager(session, user_id)
    return await manager.get_key(provider)


async def get_provider_key_auto(user_id: int, provider: str) -> Optional[str]:
    """
    Convenience function that automatically creates a database session.
    
    Use this when you don't have an existing session (e.g., in adapters).
    
    Args:
        user_id: The user ID to fetch key for
        provider: The provider name
        
    Returns:
        The decrypted API key or None if not configured
    """
    from app.infra.db.session import get_user_db_session
    
    user = {"id": user_id}
    
    async for session in get_user_db_session(user):
        return await get_provider_key(session, user_id, provider)
    
    return None
