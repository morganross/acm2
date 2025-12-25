"""
Provider-Aware Rate Limiter.

Implements global rate limiting at the ACM level to prevent 429 errors
from LLM providers. Each provider can have different limits:
- max_concurrent: Maximum concurrent requests (semaphore-based)
- min_delay_seconds: Minimum delay between requests (timestamp-based)

This module provides a centralized way to throttle API calls before
spawning FPF subprocesses, ensuring we respect provider rate limits
across all concurrent tasks.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single provider's rate limits."""
    
    name: str
    max_concurrent: int = 10  # Max concurrent requests allowed
    min_delay_seconds: float = 0.0  # Min seconds between requests
    
    # Tracking state (not config, but easier to keep here)
    last_request_time: float = 0.0  # Unix timestamp of last request start
    
    def __post_init__(self):
        if self.max_concurrent < 1:
            raise ValueError(f"max_concurrent must be >= 1, got {self.max_concurrent}")
        if self.min_delay_seconds < 0:
            raise ValueError(f"min_delay_seconds must be >= 0, got {self.min_delay_seconds}")


@dataclass
class ProviderRateLimiter:
    """
    Rate limiter for a single provider.
    
    Uses an asyncio Semaphore for concurrency limiting and timestamp
    tracking for delay enforcement.
    """
    
    config: ProviderConfig
    _semaphore: asyncio.Semaphore = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _in_flight: int = field(default=0, init=False)
    
    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._in_flight = 0
    
    async def acquire(self) -> None:
        """
        Acquire a slot for making a request.
        
        This will:
        1. Wait for a semaphore slot (concurrency limiting)
        2. Wait for min_delay since last request (rate limiting)
        3. Update tracking state
        """
        # 1. Acquire semaphore slot
        await self._semaphore.acquire()
        
        try:
            # 2. Enforce minimum delay between requests
            async with self._lock:
                now = time.time()
                elapsed = now - self.config.last_request_time
                
                if elapsed < self.config.min_delay_seconds:
                    wait_time = self.config.min_delay_seconds - elapsed
                    logger.info(
                        f"[RATE-LIMIT] Provider {self.config.name}: "
                        f"Waiting {wait_time:.1f}s (min_delay={self.config.min_delay_seconds}s, "
                        f"elapsed={elapsed:.1f}s)"
                    )
                    # Release lock during sleep so other tasks can check timing
                    # They'll also need to wait, but at least they can queue up
                    
                # We'll wait outside the lock to avoid blocking
                wait_time_needed = max(0, self.config.min_delay_seconds - elapsed)
            
            # Sleep outside lock if needed
            if wait_time_needed > 0:
                await asyncio.sleep(wait_time_needed)
            
            # 3. Update tracking state
            async with self._lock:
                self.config.last_request_time = time.time()
                self._in_flight += 1
                logger.info(
                    f"[RATE-LIMIT] Provider {self.config.name}: "
                    f"ACQUIRED slot (in_flight={self._in_flight}/{self.config.max_concurrent})"
                )
        except Exception:
            # If anything fails, release the semaphore
            self._semaphore.release()
            raise
    
    def release(self) -> None:
        """Release a request slot after completion."""
        self._in_flight = max(0, self._in_flight - 1)
        self._semaphore.release()
        logger.info(
            f"[RATE-LIMIT] Provider {self.config.name}: "
            f"RELEASED slot (in_flight={self._in_flight}/{self.config.max_concurrent})"
        )
    
    @property
    def in_flight_count(self) -> int:
        """Number of currently active requests."""
        return self._in_flight


class ProviderRegistry:
    """
    Singleton registry of all provider rate limiters.
    
    Provides a central place to manage rate limits for all providers.
    Default limits are conservative for Tier 1 API access.
    """
    
    _instance: Optional["ProviderRegistry"] = None
    _lock: asyncio.Lock = None
    
    # Default provider configurations
    # These are conservative defaults for Tier 1 API access
    DEFAULT_CONFIGS: Dict[str, Dict] = {
        "anthropic": {
            "max_concurrent": 1,  # Serial execution
            "min_delay_seconds": 61.0,  # 61s between calls (safe for 30k tokens/min)
        },
        "openai": {
            "max_concurrent": 5,  # OpenAI has higher limits
            "min_delay_seconds": 1.0,
        },
        "google": {
            "max_concurrent": 5,
            "min_delay_seconds": 1.0,
        },
        "openrouter": {
            "max_concurrent": 3,
            "min_delay_seconds": 2.0,
        },
        # Default for unknown providers
        "_default": {
            "max_concurrent": 2,
            "min_delay_seconds": 5.0,
        },
    }
    
    def __init__(self):
        self._limiters: Dict[str, ProviderRateLimiter] = {}
        self._registry_lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls) -> "ProviderRegistry":
        """Get or create the singleton instance."""
        if cls._instance is None:
            if cls._lock is None:
                cls._lock = asyncio.Lock()
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None
    
    async def _initialize(self) -> None:
        """Initialize all provider limiters from default configs."""
        for provider_name, config_dict in self.DEFAULT_CONFIGS.items():
            if provider_name == "_default":
                continue
            config = ProviderConfig(
                name=provider_name,
                max_concurrent=config_dict["max_concurrent"],
                min_delay_seconds=config_dict["min_delay_seconds"],
            )
            self._limiters[provider_name] = ProviderRateLimiter(config)
        
        logger.info(
            f"[RATE-LIMIT] Initialized ProviderRegistry with {len(self._limiters)} providers: "
            f"{list(self._limiters.keys())}"
        )
    
    async def get_limiter(self, provider: str) -> ProviderRateLimiter:
        """
        Get the rate limiter for a provider.
        
        If provider is unknown, creates a limiter with default settings.
        """
        provider_lower = provider.lower()
        
        async with self._registry_lock:
            if provider_lower not in self._limiters:
                # Create limiter with default settings
                default_config = self.DEFAULT_CONFIGS.get("_default", {})
                config = ProviderConfig(
                    name=provider_lower,
                    max_concurrent=default_config.get("max_concurrent", 2),
                    min_delay_seconds=default_config.get("min_delay_seconds", 5.0),
                )
                self._limiters[provider_lower] = ProviderRateLimiter(config)
                logger.warning(
                    f"[RATE-LIMIT] Unknown provider '{provider}', "
                    f"using default limits: max_concurrent={config.max_concurrent}, "
                    f"min_delay={config.min_delay_seconds}s"
                )
            
            return self._limiters[provider_lower]
    
    def update_limits(self, provider: str, max_concurrent: Optional[int] = None, 
                      min_delay_seconds: Optional[float] = None) -> None:
        """
        Update rate limits for a provider dynamically.
        
        This can be used to adjust limits based on:
        - User settings from the UI
        - Adaptive learning from 429 responses
        """
        provider_lower = provider.lower()
        
        if provider_lower not in self._limiters:
            logger.warning(f"[RATE-LIMIT] Cannot update limits for unknown provider: {provider}")
            return
        
        limiter = self._limiters[provider_lower]
        
        if max_concurrent is not None:
            # Note: Changing semaphore size at runtime is tricky
            # For now, just update the config - will take effect on next acquire
            limiter.config.max_concurrent = max_concurrent
            # Create new semaphore with updated size
            limiter._semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(f"[RATE-LIMIT] Updated {provider} max_concurrent to {max_concurrent}")
        
        if min_delay_seconds is not None:
            limiter.config.min_delay_seconds = min_delay_seconds
            logger.info(f"[RATE-LIMIT] Updated {provider} min_delay to {min_delay_seconds}s")
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """Get current stats for all providers."""
        return {
            name: {
                "max_concurrent": limiter.config.max_concurrent,
                "min_delay_seconds": limiter.config.min_delay_seconds,
                "in_flight": limiter.in_flight_count,
                "last_request_time": limiter.config.last_request_time,
            }
            for name, limiter in self._limiters.items()
        }


# Convenience context manager for use in code
class RateLimitedRequest:
    """
    Context manager for rate-limited requests.
    
    Usage:
        async with RateLimitedRequest("anthropic"):
            # Make your API call here
            result = await fpf_adapter.generate(...)
    """
    
    def __init__(self, provider: str):
        self.provider = provider
        self._limiter: Optional[ProviderRateLimiter] = None
    
    async def __aenter__(self):
        registry = await ProviderRegistry.get_instance()
        self._limiter = await registry.get_limiter(self.provider)
        await self._limiter.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._limiter:
            self._limiter.release()
        return False  # Don't suppress exceptions
