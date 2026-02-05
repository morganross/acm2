"""
Authentication Middleware

FastAPI dependency for authenticating requests via API key.
Uses in-memory caching to avoid repeated bcrypt checks.

NEW: Uses embedded user_id in API key format for O(1) database lookup.
No master database required - user_id is parsed from key.
"""
from fastapi import Header, HTTPException, status
from typing import Optional, Dict, Any
import logging
import time
import aiosqlite
from pathlib import Path

from app.auth.api_keys import is_valid_key_format, validate_api_key, extract_uuid
from app.auth.user_registry import get_user_db_path, user_exists, construct_db_path

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
    
    NEW FLOW (no master database):
    1. Parse user_id from API key (format: acm2_u{user_id}_{random})
    2. Open user_{uuid}.db directly
    3. Look up key hash in user's api_keys table
    4. Validate with bcrypt
    
    Usage:
        @app.get("/api/v1/runs")
        async def list_runs(user: dict = Depends(get_current_user)):
            # user is authenticated
            user_uuid = user['uuid']
    
    Args:
        x_acm2_api_key: API key from X-ACM2-API-Key header
        
    Returns:
        User dict with uuid and email (no username)
        
    Raises:
        AuthenticationError: If authentication fails
    """
    logger.info("[AUTH] ========================================")
    logger.info("[AUTH] get_current_user() called")
    logger.info("[AUTH] ========================================")
    
    # Check if key provided
    if not x_acm2_api_key:
        logger.warning("[AUTH] Request missing API key")
        raise AuthenticationError("API key required")
    
    logger.info(f"[AUTH] API key prefix: {x_acm2_api_key[:20] if len(x_acm2_api_key) >= 20 else x_acm2_api_key}...")
    
    # Check cache first (instant return if cached)
    cached_user = _get_cached_user(x_acm2_api_key)
    if cached_user:
        logger.info(f"[AUTH] Cache HIT for user {cached_user.get('id')}")
        return cached_user
    
    logger.info("[AUTH] Cache MISS, validating key...")
    
    # Validate format
    if not is_valid_key_format(x_acm2_api_key):
        logger.warning(f"[AUTH] Invalid API key format: {x_acm2_api_key[:20]}...")
        raise AuthenticationError("Invalid API key format")
    
    # Extract UUID from key (O(1) - just regex parse)
    user_uuid = extract_uuid(x_acm2_api_key)
    if user_uuid is None:
        logger.warning("[AUTH] Could not extract UUID from key")
        raise AuthenticationError("Invalid API key format")
    
    logger.info(f"[AUTH] Extracted user_uuid={user_uuid} from key")
    
    # Construct database path directly (O(1) - string concatenation)
    db_path = construct_db_path(user_uuid)
    logger.info(f"[AUTH] User database path: {db_path}")
    
    if not db_path.exists():
        logger.warning(f"[AUTH] User database does not exist: {db_path}")
        raise AuthenticationError("Invalid API key")
    
    # Look up key hash in user's database
    logger.info("[AUTH] Looking up key hash in user's database...")
    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Get all active API keys for this user (should be small number)
            cursor = await conn.execute(
                "SELECT key_hash FROM api_keys WHERE is_active = 1 AND revoked_at IS NULL"
            )
            rows = await cursor.fetchall()
            logger.info(f"[AUTH] Found {len(rows)} active API keys for user {user_uuid}")
            
            # Check each key hash (usually just 1-2 keys per user)
            valid_key_found = False
            for row in rows:
                stored_hash = row['key_hash']
                if validate_api_key(x_acm2_api_key, stored_hash):
                    valid_key_found = True
                    logger.info("[AUTH] Key hash MATCHED")
                    
                    # Update last_used_at
                    await conn.execute(
                        "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
                        (stored_hash,)
                    )
                    await conn.commit()
                    break
            
            if not valid_key_found:
                logger.warning(f"[AUTH] No matching key hash for user {user_uuid}")
                raise AuthenticationError("Invalid API key")
            
            # Get user info from user_meta table (UUID and email only - NO USERNAME)
            cursor = await conn.execute(
                "SELECT uuid, email FROM user_meta LIMIT 1"
            )
            user_meta = await cursor.fetchone()
            
            if user_meta:
                user = {
                    'uuid': user_meta['uuid'],
                    'email': user_meta['email']
                }
            else:
                # Fallback if no user_meta - use UUID from key
                user = {
                    'uuid': user_uuid,
                    'email': None
                }
            
            logger.info(f"[AUTH] User authenticated: {user}")
    
    except aiosqlite.Error as e:
        logger.error(f"[AUTH] Database error: {e}")
        raise AuthenticationError("Authentication failed")
    
    # Cache the authenticated user for future requests
    _cache_user(x_acm2_api_key, user)
    logger.info(f"[AUTH] Cached user {user_uuid}")
    
    logger.info("[AUTH] ========================================")
    logger.info(f"[AUTH] SUCCESS: Authenticated user {user_uuid}")
    logger.info("[AUTH] ========================================")
    
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
