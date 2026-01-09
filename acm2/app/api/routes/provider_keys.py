"""
Provider Keys API Routes

Endpoints for managing LLM provider API keys.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import logging

from acm2.app.auth.middleware import get_current_user
from acm2.app.security.provider_keys import get_provider_key_manager, ProviderKeyManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/provider-keys", tags=["provider-keys"])


# Pydantic models
class ProviderKeyCreate(BaseModel):
    """Request to save a provider API key."""
    provider: str = Field(..., description="Provider name (openai, anthropic, google)")
    api_key: str = Field(..., description="API key for the provider", min_length=1)


class ProviderKeyInfo(BaseModel):
    """Information about a configured provider (without exposing the actual key)."""
    provider: str
    configured: bool
    key_prefix: Optional[str] = None  # First few chars for verification


class ProviderKeysList(BaseModel):
    """List of configured providers."""
    providers: List[str]


# Routes
@router.post("/", status_code=status.HTTP_201_CREATED)
async def save_provider_key(
    key_data: ProviderKeyCreate,
    user: dict = Depends(get_current_user)
):
    """Save a provider API key (encrypted).
    
    The key will be encrypted before storage and only decrypted when needed
    to call the LLM API.
    """
    user_id = user['id']
    key_manager = await get_provider_key_manager(user_id)
    
    try:
        await key_manager.save_key(key_data.provider, key_data.api_key)
        return {
            "message": f"{key_data.provider.title()} API key saved successfully",
            "provider": key_data.provider
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to save {key_data.provider} key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save API key"
        )


@router.get("/", response_model=ProviderKeysList)
async def list_provider_keys(user: dict = Depends(get_current_user)):
    """List all configured providers (without exposing the actual keys)."""
    user_id = user['id']
    key_manager = await get_provider_key_manager(user_id)
    
    try:
        providers = await key_manager.list_configured_providers()
        return ProviderKeysList(providers=providers)
    except Exception as e:
        logger.error(f"Failed to list provider keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider keys"
        )


@router.get("/{provider}", response_model=ProviderKeyInfo)
async def get_provider_key_info(
    provider: str,
    user: dict = Depends(get_current_user)
):
    """Check if a provider key is configured (without exposing the actual key)."""
    user_id = user['id']
    key_manager = await get_provider_key_manager(user_id)
    
    try:
        has_key = await key_manager.has_key(provider)
        
        # Optionally get key prefix for verification (first 8 chars)
        key_prefix = None
        if has_key:
            full_key = await key_manager.get_key(provider)
            if full_key and len(full_key) > 8:
                key_prefix = full_key[:8] + "..."
        
        return ProviderKeyInfo(
            provider=provider,
            configured=has_key,
            key_prefix=key_prefix
        )
    except Exception as e:
        logger.error(f"Failed to get {provider} key info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider key info"
        )


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
    provider: str,
    user: dict = Depends(get_current_user)
):
    """Delete a provider API key."""
    user_id = user['id']
    key_manager = await get_provider_key_manager(user_id)
    
    try:
        # Check if key exists
        if not await key_manager.has_key(provider):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider} key configured"
            )
        
        await key_manager.delete_key(provider)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete {provider} key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete provider key"
        )


@router.get("/test/{provider}")
async def test_provider_key(
    provider: str,
    user: dict = Depends(get_current_user)
):
    """Test if a provider key is valid by making a simple API call.
    
    This is useful for validating keys after configuration.
    """
    user_id = user['id']
    key_manager = await get_provider_key_manager(user_id)
    
    try:
        api_key = await key_manager.get_key(provider)
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {provider} key configured"
            )
        
        # TODO: Implement actual API test calls for each provider
        # For now, just check if key exists and can be decrypted
        return {
            "provider": provider,
            "status": "configured",
            "message": f"{provider.title()} API key is configured and accessible"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test {provider} key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test {provider} key"
        )
