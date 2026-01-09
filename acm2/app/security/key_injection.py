"""
Provider Key Injection Service

This module provides functionality to inject decrypted provider API keys
into the environment for LLM adapters. Keys are fetched from the user's
encrypted database and temporarily injected into process environment.
"""
import os
from typing import Dict
from app.security.provider_keys import ProviderKeyManager


async def inject_provider_keys_for_user(user_id: int, env: Dict[str, str]) -> Dict[str, str]:
    """
    Fetch and inject all configured provider API keys for a user into an environment dict.
    
    Args:
        user_id: The user ID to fetch keys for
        env: The environment dictionary to inject keys into (typically os.environ.copy())
    
    Returns:
        The updated environment dictionary with provider keys injected
        
    Example:
        env = os.environ.copy()
        env = await inject_provider_keys_for_user(user_id=1, env=env)
        # Now env contains OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
    """
    manager = ProviderKeyManager(user_id)
    
    # Map provider names to environment variable names
    provider_to_env_var = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    
    # Get all configured providers
    configured_providers = await manager.get_all_keys()
    
    # Inject each provider's key
    for provider in configured_providers:
        env_var = provider_to_env_var.get(provider)
        if env_var:
            key = await manager.get_key(provider)
            if key:
                env[env_var] = key
    
    return env


async def get_provider_key(user_id: int, provider: str) -> str | None:
    """
    Get a single decrypted provider API key for a user.
    
    Args:
        user_id: The user ID to fetch key for
        provider: The provider name (openai, anthropic, google)
    
    Returns:
        The decrypted API key or None if not configured
        
    Example:
        openai_key = await get_provider_key(user_id=1, provider="openai")
        if openai_key:
            client = OpenAI(api_key=openai_key)
    """
    manager = ProviderKeyManager(user_id)
    return await manager.get_key(provider)
