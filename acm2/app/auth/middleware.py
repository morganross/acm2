"""
Authentication Middleware

FastAPI dependency for authenticating requests via API key.
Uses in-memory caching to avoid repeated bcrypt checks.
"""
from fastapi import Header, HTTPException, status
from typing import Optional, Dict, Any
import logging
import time

from app.db.master import get_master_db
from app.auth.api_keys import is_valid_key_format, validate_api_key

logger = logging.getLogger(__name__)

# In-memory cache: api_key -> (user_dict, expiry_timestamp)
# Keys are cached for 5 minutes after successful validation
_auth_cache: Dict[str, tuple] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_user(api_key: str) -> Optional[Dict[str, Any]]:
    """Get user from cache if valid and not expired."""
    if api_key in _auth_cache:
        user, expiry = _auth_cache[api_key]
        if time.time() < expiry:
            return user
        # Expired, remove from cache
        del _auth_cache[api_key]
    return None


def _cache_user(api_key: str, user: Dict[str, Any]) -> None:
    """Cache authenticated user."""
    _auth_cache[api_key] = (user, time.time() + _CACHE_TTL_SECONDS)


def clear_auth_cache() -> None:
    """Clear the auth cache (call when API keys are revoked)."""
    _auth_cache.clear()


class AuthenticationError(HTTPException):
    """Authentication failed."""
    def __init__(self, detail: str = "Invalid or missing API key"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    x_acm2_api_key: Optional[str] = Header(None, alias="X-ACM2-API-Key")
) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user.
    
    Uses in-memory caching to avoid repeated DB lookups and bcrypt checks.
    
    Usage:
        @app.get("/api/v1/runs")
        async def list_runs(user: dict = Depends(get_current_user)):
            # user is authenticated
            user_id = user['id']
    
    Args:
        x_acm2_api_key: API key from X-ACM2-API-Key header
        
    Returns:
        User dict from master database
        
    Raises:
        AuthenticationError: If authentication fails
    """
    # Check if key provided
    if not x_acm2_api_key:
        logger.warning("Request missing API key")
        raise AuthenticationError("API key required")
    
    # Check cache first (instant return if cached)
    cached_user = _get_cached_user(x_acm2_api_key)
    if cached_user:
        return cached_user
    
    # Validate format
    if not is_valid_key_format(x_acm2_api_key):
        logger.warning(f"Invalid API key format: {x_acm2_api_key[:12]}...")
        raise AuthenticationError("Invalid API key format")
    
    # Extract key prefix for efficient lookup (first 12 chars)
    key_prefix = x_acm2_api_key[:12]
    
    # Get master database
    master_db = await get_master_db()
    
    # Look up the specific key by prefix (single row, single bcrypt check)
    async with master_db.get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT key_hash, user_id FROM api_keys WHERE key_prefix = %s AND revoked_at IS NULL",
                (key_prefix,)
            )
            row = await cursor.fetchone()
    
    if not row:
        logger.warning(f"No API key found with prefix: {key_prefix}...")
        raise AuthenticationError("Invalid API key")
    
    stored_hash, user_id = row
    
    # Single bcrypt check against the matching key
    if not validate_api_key(x_acm2_api_key, stored_hash):
        logger.warning(f"Invalid API key (hash mismatch): {key_prefix}...")
        raise AuthenticationError("Invalid API key")
    
    # Get user from master database and update last_used_at
    user = await master_db.get_user_by_api_key_hash(stored_hash)
    
    if not user:
        logger.error(f"User not found for valid API key (user_id: {user_id})")
        raise AuthenticationError("User not found")
    
    # Cache the authenticated user for future requests
    _cache_user(x_acm2_api_key, user)
    
    logger.info(f"Authenticated user {user_id} ({user.get('username', 'unknown')})")
    return user


async def get_optional_user(
    x_acm2_api_key: Optional[str] = Header(None, alias="X-ACM2-API-Key")
) -> Optional[Dict[str, Any]]:
    """Optional authentication - returns None if no key provided.
    
    Usage:
        @app.get("/api/v1/public")
        async def public_endpoint(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                # Authenticated
            else:
                # Anonymous
    """
    if not x_acm2_api_key:
        return None
    
    try:
        return await get_current_user(x_acm2_api_key)
    except AuthenticationError:
        return None
