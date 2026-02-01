"""
User Registry - In-Memory User ID to Database Path Mapping

Provides O(1) lookup from user_id to database file path.
Loaded at startup by scanning data/user_*.db files.
Updated when new users are created.

EXTREME LOGGING ENABLED.
"""
import re
from pathlib import Path
from typing import Dict, Optional, Set
import logging
import traceback

logger = logging.getLogger(__name__)

# In-memory registry: user_id -> db_path
_user_registry: Dict[int, Path] = {}

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
        
        # Pattern: user_123.db
        pattern = re.compile(r'^user_(\d+)\.db$')
        
        # Scan for user database files
        db_files = list(data_dir.glob("user_*.db"))
        logger.info(f"[USER_REGISTRY] Found {len(db_files)} potential user DB files")
        
        for db_path in db_files:
            match = pattern.match(db_path.name)
            if match:
                user_id = int(match.group(1))
                _user_registry[user_id] = db_path
                logger.info(f"[USER_REGISTRY] Registered user {user_id} -> {db_path.name}")
            else:
                logger.warning(f"[USER_REGISTRY] Skipping non-matching file: {db_path.name}")
        
        user_count = len(_user_registry)
        logger.info("[USER_REGISTRY] ========================================")
        logger.info(f"[USER_REGISTRY] load_registry() COMPLETE: {user_count} users loaded")
        logger.info(f"[USER_REGISTRY] Registered user IDs: {sorted(_user_registry.keys())}")
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


def register_user(user_id: int) -> Path:
    """
    Register a new user in the registry.
    Called when a new user is created.
    
    Args:
        user_id: The user's ID (from wordpress_user_id or auto-generated)
        
    Returns:
        Path to the user's database file
    """
    logger.info("[USER_REGISTRY] ========================================")
    logger.info(f"[USER_REGISTRY] register_user() called with user_id={user_id}")
    logger.info("[USER_REGISTRY] ========================================")
    
    try:
        data_dir = get_data_dir()
        db_path = data_dir / f"user_{user_id}.db"
        
        logger.info(f"[USER_REGISTRY] Database path will be: {db_path}")
        
        # Add to registry
        _user_registry[user_id] = db_path
        logger.info(f"[USER_REGISTRY] Added user {user_id} to registry")
        logger.info(f"[USER_REGISTRY] Registry now has {len(_user_registry)} users")
        
        return db_path
        
    except Exception as e:
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        logger.error(f"[USER_REGISTRY] ERROR in register_user({user_id})")
        logger.error(f"[USER_REGISTRY] Exception: {str(e)}")
        logger.error(f"[USER_REGISTRY] Traceback:\n{traceback.format_exc()}")
        logger.error("[USER_REGISTRY] !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        raise


def get_user_db_path(user_id: int) -> Optional[Path]:
    """
    Get database path for a user.
    O(1) lookup from in-memory registry.
    
    Args:
        user_id: The user's ID
        
    Returns:
        Path to user's database file, or None if not found
    """
    logger.debug(f"[USER_REGISTRY] get_user_db_path({user_id}) - looking up...")
    
    db_path = _user_registry.get(user_id)
    
    if db_path:
        logger.debug(f"[USER_REGISTRY] Found: {db_path}")
    else:
        logger.warning(f"[USER_REGISTRY] User {user_id} NOT found in registry")
        
    return db_path


def user_exists(user_id: int) -> bool:
    """Check if a user exists in the registry."""
    exists = user_id in _user_registry
    logger.debug(f"[USER_REGISTRY] user_exists({user_id}) = {exists}")
    return exists


def get_user_count() -> int:
    """Get total number of registered users."""
    count = len(_user_registry)
    logger.info(f"[USER_REGISTRY] get_user_count() = {count}")
    return count


def get_all_user_ids() -> Set[int]:
    """Get set of all registered user IDs."""
    return set(_user_registry.keys())


def unregister_user(user_id: int) -> bool:
    """
    Remove a user from the registry.
    Called when a user is deleted.
    
    Returns:
        True if user was removed, False if not found
    """
    logger.info(f"[USER_REGISTRY] unregister_user({user_id}) called")
    
    if user_id in _user_registry:
        del _user_registry[user_id]
        logger.info(f"[USER_REGISTRY] User {user_id} removed from registry")
        return True
    else:
        logger.warning(f"[USER_REGISTRY] User {user_id} not found in registry")
        return False


def construct_db_path(user_id: int) -> Path:
    """
    Construct the database path for a user ID.
    Does NOT check if user exists - use for new user creation.
    
    This is the predictable naming: user_{id}.db
    """
    data_dir = get_data_dir()
    return data_dir / f"user_{user_id}.db"
