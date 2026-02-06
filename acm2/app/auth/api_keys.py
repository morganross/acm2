"""
API Key Management

Generates and validates ACM2 API keys for user authentication.

KEY FORMAT: acm2_{uuid}_{random}
Example: acm2_550e8400-e29b-41d4-a716-446655440000_kKDHtSEDaGB

The UUID is embedded in the key for O(1) database file lookup.
No master database needed - parse key, construct path, validate hash.

UUID ONLY - No bland usernames, no integer user IDs.

EXTREME LOGGING ENABLED.
"""
import secrets
import bcrypt
import re
from typing import Tuple, Optional
import logging
import traceback

logger = logging.getLogger(__name__)

# API key format: acm2_{uuid}_{random}
API_KEY_PREFIX = "acm2_"
API_KEY_RANDOM_LENGTH = 16  # Shorter random part since UUID is long

# Regex to parse key format: acm2_{uuid}_{random}
# UUID format: 8-4-4-4-12 hex digits
API_KEY_PATTERN = re.compile(r'^acm2_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})_([A-Za-z0-9_-]+)$', re.IGNORECASE)


def generate_api_key(user_uuid: str) -> Tuple[str, str, str]:
    """Generate a new API key for a specific user.
    
    Args:
        user_uuid: The user's UUID to embed in the key (e.g., "550e8400-e29b-41d4-a716-446655440000")
    
    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: The actual key to give to user (only shown once)
        - key_hash: bcrypt hash to store in user's database
        - key_prefix: Display prefix (e.g., "acm2_550e8400-...")
    """
    logger.info("[API_KEYS] ========================================")
    logger.info(f"[API_KEYS] generate_api_key() called for uuid={user_uuid}")
    logger.info("[API_KEYS] ========================================")
    
    try:
        # Generate random token
        logger.info("[API_KEYS] Step 1: Generating random token...")
        logger.info(f"[API_KEYS] API_KEY_RANDOM_LENGTH = {API_KEY_RANDOM_LENGTH}")
        random_part = secrets.token_urlsafe(API_KEY_RANDOM_LENGTH)[:API_KEY_RANDOM_LENGTH]
        logger.info(f"[API_KEYS] Random part generated: {random_part[:8]}... (length: {len(random_part)})")
        
        # Format: acm2_{uuid}_{random}
        full_key = f"{API_KEY_PREFIX}{user_uuid}_{random_part}"
        logger.info(f"[API_KEYS] Full key created: {full_key[:30]}... (length: {len(full_key)})")
        
        # Create bcrypt hash
        logger.info("[API_KEYS] Step 2: Creating bcrypt hash...")
        logger.info("[API_KEYS] Generating salt...")
        salt = bcrypt.gensalt()
        logger.info(f"[API_KEYS] Salt generated (length: {len(salt)})")
        
        logger.info("[API_KEYS] Hashing key with bcrypt...")
        key_hash = bcrypt.hashpw(full_key.encode('utf-8'), salt).decode('utf-8')
        logger.info(f"[API_KEYS] Key hash created: {key_hash[:20]}... (length: {len(key_hash)})")
        
        # Create prefix for display (first 20 chars or so)
        logger.info("[API_KEYS] Step 3: Creating key prefix for display...")
        key_prefix = full_key[:20]  # "acm2_u42_kKDHtSEDaGB"
        logger.info(f"[API_KEYS] Key prefix: {key_prefix}")
        
        logger.info("[API_KEYS] ========================================")
        logger.info("[API_KEYS] generate_api_key() SUCCESS")
        logger.info(f"[API_KEYS] Key format: acm2_{user_uuid}_<random>")
        logger.info(f"[API_KEYS] Returning: (full_key={full_key[:30]}..., key_hash={key_hash[:20]}..., key_prefix={key_prefix})")
        logger.info("[API_KEYS] ========================================")
        
        return full_key, key_hash, key_prefix
        
    except Exception as e:
        logger.error("[API_KEYS] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error("[API_KEYS] FATAL ERROR in generate_api_key()")
        logger.error(f"[API_KEYS] Exception type: {type(e).__name__}")
        logger.error(f"[API_KEYS] Exception message: {str(e)}")
        logger.error(f"[API_KEYS] Traceback:\n{traceback.format_exc()}")
        logger.error("[API_KEYS] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        raise


def parse_api_key(key: str) -> Optional[Tuple[str, str]]:
    """Parse an API key to extract UUID and random part.
    
    Args:
        key: The full API key (e.g., "acm2_550e8400-e29b-41d4-a716-446655440000_kKDHtSE")
        
    Returns:
        Tuple of (uuid, random_part) or None if invalid format
    """
    logger.debug(f"[API_KEYS] parse_api_key() called with key prefix: {key[:30] if len(key) >= 30 else key}")
    
    match = API_KEY_PATTERN.match(key)
    if match:
        user_uuid = match.group(1).lower()  # Normalize UUID to lowercase
        random_part = match.group(2)
        logger.debug(f"[API_KEYS] Parsed: uuid={user_uuid}, random_part={random_part[:8]}...")
        return user_uuid, random_part
    else:
        logger.warning(f"[API_KEYS] Failed to parse key: {key[:30] if len(key) >= 30 else key}...")
        return None


def extract_uuid(key: str) -> Optional[str]:
    """Extract just the UUID from an API key.
    
    Args:
        key: The full API key
        
    Returns:
        The UUID string (lowercase) or None if invalid format
    """
    result = parse_api_key(key)
    if result:
        return result[0]
    return None


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Validate an API key against its stored hash.
    
    Args:
        provided_key: The key provided by the client
        stored_hash: The bcrypt hash from database
        
    Returns:
        True if key is valid
    """
    logger.info("[API_KEYS] ========================================")
    logger.info("[API_KEYS] verify_api_key() called")
    logger.info("[API_KEYS] ========================================")
    logger.info(f"[API_KEYS] provided_key prefix: {provided_key[:20] if len(provided_key) >= 20 else provided_key}")
    logger.info(f"[API_KEYS] provided_key length: {len(provided_key)}")
    logger.info(f"[API_KEYS] stored_hash prefix: {stored_hash[:20]}...")
    logger.info(f"[API_KEYS] stored_hash length: {len(stored_hash)}")
    
    try:
        logger.info("[API_KEYS] Calling bcrypt.checkpw()...")
        result = bcrypt.checkpw(
            provided_key.encode('utf-8'),
            stored_hash.encode('utf-8')
        )
        logger.info(f"[API_KEYS] bcrypt.checkpw() returned: {result}")
        
        if result:
            logger.info("[API_KEYS] verify_api_key() SUCCESS: Key is VALID")
        else:
            logger.warning("[API_KEYS] verify_api_key(): Key is INVALID (hash mismatch)")
        
        return result
        
    except Exception as e:
        logger.error("[API_KEYS] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error("[API_KEYS] ERROR in verify_api_key()")
        logger.error(f"[API_KEYS] Exception type: {type(e).__name__}")
        logger.error(f"[API_KEYS] Exception message: {str(e)}")
        logger.error(f"[API_KEYS] Traceback:\n{traceback.format_exc()}")
        logger.error("[API_KEYS] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        return False


# Alias for backward compatibility
validate_api_key = verify_api_key


def is_valid_key_format(key: str) -> bool:
    """Check if key has valid format (UUID-based format).
    
    Args:
        key: API key to check
        
    Returns:
        True if format is correct (acm2_{uuid}_{random})
    """
    logger.info(f"[API_KEYS] is_valid_key_format() called with key prefix: {key[:30] if len(key) >= 30 else key}")
    
    # Check UUID format: acm2_{uuid}_{random}
    if API_KEY_PATTERN.match(key):
        logger.info("[API_KEYS] is_valid_key_format() - format is VALID (UUID format)")
        return True
    
    logger.warning("[API_KEYS] is_valid_key_format() - format is INVALID")
    return False
