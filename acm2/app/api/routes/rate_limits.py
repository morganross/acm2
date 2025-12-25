"""
Rate Limiter API Routes.

Provides endpoints for viewing and modifying provider rate limit settings.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.rate_limiter import ProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])


class ProviderLimitsResponse(BaseModel):
    """Response model for provider rate limits."""
    
    name: str
    max_concurrent: int = Field(description="Maximum concurrent requests")
    min_delay_seconds: float = Field(description="Minimum delay between requests in seconds")
    in_flight: int = Field(description="Currently active requests")
    last_request_time: float = Field(description="Unix timestamp of last request")


class AllProvidersResponse(BaseModel):
    """Response model for all provider rate limits."""
    
    providers: Dict[str, ProviderLimitsResponse]


class UpdateLimitsRequest(BaseModel):
    """Request model for updating provider limits."""
    
    max_concurrent: Optional[int] = Field(
        default=None, 
        ge=1, 
        le=50,
        description="Maximum concurrent requests (1-50)"
    )
    min_delay_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Minimum delay between requests in seconds (0-300)"
    )


@router.get("", response_model=AllProvidersResponse)
async def get_all_rate_limits():
    """
    Get rate limit settings for all configured providers.
    
    Returns current limits and in-flight request counts for each provider.
    """
    try:
        registry = await ProviderRegistry.get_instance()
        stats = registry.get_all_stats()
        
        providers = {}
        for name, data in stats.items():
            providers[name] = ProviderLimitsResponse(
                name=name,
                max_concurrent=data["max_concurrent"],
                min_delay_seconds=data["min_delay_seconds"],
                in_flight=data["in_flight"],
                last_request_time=data["last_request_time"],
            )
        
        return AllProvidersResponse(providers=providers)
    except Exception as e:
        logger.error(f"Error getting rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider}", response_model=ProviderLimitsResponse)
async def get_provider_rate_limits(provider: str):
    """
    Get rate limit settings for a specific provider.
    
    Args:
        provider: Provider name (e.g., 'anthropic', 'openai')
    """
    try:
        registry = await ProviderRegistry.get_instance()
        stats = registry.get_all_stats()
        
        provider_lower = provider.lower()
        if provider_lower not in stats:
            raise HTTPException(
                status_code=404, 
                detail=f"Provider '{provider}' not found. Available: {list(stats.keys())}"
            )
        
        data = stats[provider_lower]
        return ProviderLimitsResponse(
            name=provider_lower,
            max_concurrent=data["max_concurrent"],
            min_delay_seconds=data["min_delay_seconds"],
            in_flight=data["in_flight"],
            last_request_time=data["last_request_time"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rate limits for {provider}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{provider}", response_model=ProviderLimitsResponse)
async def update_provider_rate_limits(provider: str, request: UpdateLimitsRequest):
    """
    Update rate limit settings for a specific provider.
    
    Args:
        provider: Provider name (e.g., 'anthropic', 'openai')
        request: New limit settings
        
    Note: Changes take effect immediately for new requests.
    In-flight requests will complete with old settings.
    """
    try:
        registry = await ProviderRegistry.get_instance()
        
        # Ensure provider exists (this will create it with defaults if not)
        await registry.get_limiter(provider)
        
        # Update limits
        registry.update_limits(
            provider=provider,
            max_concurrent=request.max_concurrent,
            min_delay_seconds=request.min_delay_seconds,
        )
        
        # Return updated settings
        stats = registry.get_all_stats()
        provider_lower = provider.lower()
        data = stats[provider_lower]
        
        logger.info(
            f"Updated rate limits for {provider}: "
            f"max_concurrent={request.max_concurrent}, "
            f"min_delay_seconds={request.min_delay_seconds}"
        )
        
        return ProviderLimitsResponse(
            name=provider_lower,
            max_concurrent=data["max_concurrent"],
            min_delay_seconds=data["min_delay_seconds"],
            in_flight=data["in_flight"],
            last_request_time=data["last_request_time"],
        )
    except Exception as e:
        logger.error(f"Error updating rate limits for {provider}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
