"""
API Key Management

Generates and validates ACM2 API keys for user authentication.
"""
import secrets
import bcrypt
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# API key format: acm2_<32 random chars>
API_KEY_PREFIX = "acm2_"
API_KEY_LENGTH = 32  # Characters after prefix


def generate_api_key() -> Tuple[str, str, str]:
    """Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: The actual key to give to user (only shown once)
        - key_hash: bcrypt hash to store in database
        - key_prefix: First 8 chars for display (e.g., "acm2_abc")
    """
    # Generate random token
    random_part = secrets.token_urlsafe(API_KEY_LENGTH)[:API_KEY_LENGTH]
    full_key = f"{API_KEY_PREFIX}{random_part}"
    
    # Create bcrypt hash
    key_hash = bcrypt.hashpw(full_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create prefix for display
    key_prefix = full_key[:12]  # "acm2_abc1234"
    
    logger.info(f"Generated API key with prefix: {key_prefix}...")
    
    return full_key, key_hash, key_prefix


def validate_api_key(provided_key: str, stored_hash: str) -> bool:
    """Validate an API key against its stored hash.
    
    Args:
        provided_key: The key provided by the client
        stored_hash: The bcrypt hash from database
        
    Returns:
        True if key is valid
    """
    try:
        return bcrypt.checkpw(
            provided_key.encode('utf-8'),
            stored_hash.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        return False


def is_valid_key_format(key: str) -> bool:
    """Check if key has valid format.
    
    Args:
        key: API key to check
        
    Returns:
        True if format is correct
    """
    if not key.startswith(API_KEY_PREFIX):
        return False
    
    if len(key) != len(API_KEY_PREFIX) + API_KEY_LENGTH:
        return False
    
    # Check that remaining chars are alphanumeric + _-
    remaining = key[len(API_KEY_PREFIX):]
    return all(c.isalnum() or c in '_-' for c in remaining)
