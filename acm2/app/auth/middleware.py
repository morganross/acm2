"""
Authentication Middleware

FastAPI dependency for authenticating requests via API key.
"""
from fastapi import Header, HTTPException, status
from typing import Optional, Dict, Any
import logging

from app.db.master import get_master_db
from app.auth.api_keys import is_valid_key_format, validate_api_key

logger = logging.getLogger(__name__)


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
    
    # Validate format
    if not is_valid_key_format(x_acm2_api_key):
        logger.warning(f"Invalid API key format: {x_acm2_api_key[:12]}...")
        raise AuthenticationError("Invalid API key format")
    
    # Get master database
    master_db = await get_master_db()
    
    # Look up all active API keys and check each one
    # (In production, you might want to optimize this with a cache)
    async with master_db.get_connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT key_hash, user_id FROM api_keys WHERE revoked_at IS NULL"
            )
            keys = await cursor.fetchall()
    
    # Check provided key against each stored hash
    user_id = None
    key_hash = None
    for stored_hash, uid in keys:
        if validate_api_key(x_acm2_api_key, stored_hash):
            user_id = uid
            key_hash = stored_hash
            break
    
    if not user_id:
        logger.warning(f"Invalid API key: {x_acm2_api_key[:12]}...")
        raise AuthenticationError("Invalid API key")
    
    # Get user from master database and update last_used_at
    user = await master_db.get_user_by_api_key_hash(key_hash)
    
    if not user:
        logger.error(f"User not found for valid API key (user_id: {user_id})")
        raise AuthenticationError("User not found")
    
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
