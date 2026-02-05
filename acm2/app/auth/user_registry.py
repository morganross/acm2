"""
User Registry - In-Memory UUID to Database Path Mapping

Provides O(1) lookup from user UUID to database file path.
Loaded at startup by scanning data/user_*.db files (UUID-based naming).
Updated when new users are created.

UUID ONLY - No integer user IDs, no bland usernames.

EXTREME LOGGING ENABLED.
"""
import re
from pathlib import Path
from typing import Dict, Optional, Set
import logging
import traceback

logger = logging.getLogger(__name__)

# In-memory registry: uuid -> db_path
_user_registry: Dict[str, Path] = {}

# Data directory path
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def get_data_dir() -> Path:
    """Get the data directory path, creating it if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def load_registry() -> int:
    """
    Scan data directory for user_*.db files and populate registry.
    Called once at application startup.
    
    Database naming: user_{uuid}.db
    Example: user_550e8400-e29b-41d4-a716-446655440000.db
    
    Returns:
        Number of users loaded
    """
    global _user_registry
    
    logger.info("[USER_REGISTRY] ========================================")
    logger.info("[USER_REGISTRY] load_registry() called")
    logger.info("[USER_REGISTRY] ========================================")
    
    try:
        data_dir = get_data_dir()
        logger.info(f"[USER_REGISTRY] Scanning directory: {data_dir}")
        
        # Clear existing registry
        _user_registry.clear()
        logger.info("[USER_REGISTRY] Cleared existing registry")
        
        # Pattern: user_{uuid}.db where uuid is 8-4-4-4-12 hex digits
        pattern = re.compile(r'^user_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.db$', re.IGNORECASE)
        
        # Scan for user database files
        db_files = list(data_dir.glob("user_*.db"))
        logger.info(f"[USER_REGISTRY] Found {len(db_files)} potential user DB files")
        
        for db_path in db_files:
            match = pattern.match(db_path.name)
            if match:
                user_uuid = match.group(1).lower()  # Normalize to lowercase
                _user_registry[user_uuid] = db_path
                logger.info(f"[USER_REGISTRY] Registered user {user_uuid} -> {db_path.name}")
            else:
                logger.warning(f"[USER_REGISTRY] Skipping non-matching file: {db_path.name}")
        
        user_count = len(_user_registry)
        logger.info("[USER_REGISTRY] ========================================")
        logger.info(f"[USER_REGISTRY] load_registry() COMPLETE: {user_count} users loaded")
        logger.info(f"[USER_REGISTRY] Registered UUIDs: {list(_user_registry.keys())}")
        logger.info("[USER_REGISTRY] ========================================")
        
        return user_count
        
    except Exception as e:
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error("[USER_REGISTRY] FATAL ERROR in load_registry()")
        logger.error(f"[USER_REGISTRY] Exception type: {type(e).__name__}")
        logger.error(f"[USER_REGISTRY] Exception message: {str(e)}")
        logger.error(f"[USER_REGISTRY] Traceback:\n{traceback.format_exc()}")
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        raise


def register_user(user_uuid: str) -> Path:
    """
    Register a new user in the registry.
    Called when a new user is created.
    
    Args:
        user_uuid: The user's UUID (from WordPress frontend)
        
    Returns:
        Path to the user's database file
    """
    logger.info("[USER_REGISTRY] ========================================")
    logger.info(f"[USER_REGISTRY] register_user() called with uuid={user_uuid}")
    logger.info("[USER_REGISTRY] ========================================")
    
    try:
        # Normalize UUID to lowercase
        user_uuid = user_uuid.lower()
        
        data_dir = get_data_dir()
        db_path = data_dir / f"user_{user_uuid}.db"
        
        logger.info(f"[USER_REGISTRY] Database path will be: {db_path}")
        
        # Add to registry
        _user_registry[user_uuid] = db_path
        logger.info(f"[USER_REGISTRY] Added user {user_uuid} to registry")
        logger.info(f"[USER_REGISTRY] Registry now has {len(_user_registry)} users")
        
        return db_path
        
    except Exception as e:
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error(f"[USER_REGISTRY] ERROR in register_user({user_id})")
        logger.error(f"[USER_REGISTRY] Exception: {str(e)}")
        logger.error(f"[USER_REGISTRY] Traceback:\n{traceback.format_exc()}")
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        raise


def get_user_db_path(user_uuid: str) -> Optional[Path]:
    """
    Get database path for a user.
    O(1) lookup from in-memory registry.
    
    Args:
        user_uuid: The user's UUID
        
    Returns:
        Path to user's database file, or None if not found
    """
    # Normalize to lowercase
    user_uuid = user_uuid.lower()
    
    logger.debug(f"[USER_REGISTRY] get_user_db_path({user_uuid}) - looking up...")
    
    db_path = _user_registry.get(user_uuid)
    
    if db_path:
        logger.debug(f"[USER_REGISTRY] Found: {db_path}")
    else:
        logger.warning(f"[USER_REGISTRY] User {user_uuid} NOT found in registry")
        
    return db_path


def user_exists(user_uuid: str) -> bool:
    """Check if a user exists in the registry."""
    user_uuid = user_uuid.lower()
    exists = user_uuid in _user_registry
    logger.debug(f"[USER_REGISTRY] user_exists({user_uuid}) = {exists}")
    return exists
    return exists


def get_user_count() -> int:
    """Get total number of registered users."""
    count = len(_user_registry)
    logger.info(f"[USER_REGISTRY] get_user_count() = {count}")
    return count


def get_all_user_uuids() -> Set[str]:
    """Get set of all registered user UUIDs."""
    return set(_user_registry.keys())


# Backwards compatibility alias
def get_all_user_ids() -> Set[str]:
    """DEPRECATED: Use get_all_user_uuids instead."""
    return get_all_user_uuids()


def unregister_user(user_uuid: str) -> bool:
    """
    Remove a user from the registry.
    Called when a user is deleted.
    
    Returns:
        True if user was removed, False if not found
    """
    user_uuid = user_uuid.lower()
    logger.info(f"[USER_REGISTRY] unregister_user({user_uuid}) called")
    
    if user_uuid in _user_registry:
        del _user_registry[user_uuid]
        logger.info(f"[USER_REGISTRY] User {user_uuid} removed from registry")
        return True
    else:
        logger.warning(f"[USER_REGISTRY] User {user_uuid} not found in registry")
        return False


def construct_db_path(user_uuid: str) -> Path:
    """
    Construct the database path for a user UUID.
    Does NOT check if user exists - use for new user creation.
    
    This is the predictable naming: user_{uuid}.db
    """
    user_uuid = user_uuid.lower()
    data_dir = get_data_dir()
    return data_dir / f"user_{user_uuid}.db"
