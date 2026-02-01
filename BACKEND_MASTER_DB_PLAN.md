# Backend Master DB Plan: SQLite Key-to-User Lookup

## Goal

Create a local SQLite `master.db` on the backend that maps API keys to user IDs. This eliminates the need for cross-network MySQL connections.

---

## Architecture

```
Frontend (Bitnami)                    Backend (Windows)
┌─────────────────────────┐          ┌─────────────────────────────────┐
│ WordPress               │          │ FastAPI                         │
│                         │          │                                 │
│ wp-config.php:          │          │ .env:                           │
│ - ACM2_PLUGIN_SECRET    │◄────────►│ - ACM2_PLUGIN_SECRET            │
│   (shared secret)       │  (match) │   (same value)                  │
│                         │          │                                 │
│ MySQL (frontend.master):│          │ data/master.db (backend.master) │
│ - wp_usermeta           │          │ ├── users (id, wordpress_id)    │
│   acm2_api_key_enc      │          │ └── api_keys (hash → user_id)   │
│   (encrypted with       │          │                                 │
│    AUTH_KEY salt)       │          │ data/user_6.db (SQLite)         │
│                         │          │ └── presets, runs, provider_keys│
│ No backend connection   │          │                                 │
│ to this MySQL!          │          │ data/user_7.db (SQLite)         │
└─────────────────────────┘          └─────────────────────────────────┘
```

---

## Two Types of Keys

| Key Type | Purpose | Who Uses It | Stored Where |
|----------|---------|-------------|---------------|
| **Plugin Secret** | Authorizes WordPress to create users | WordPress plugin only | wp-config.php + backend .env |
| **User API Key** | Authorizes React to make API calls | React app (per user) | frontend.master (encrypted) + backend.master (hashed) |

---

## Plugin Secret Setup

The plugin secret solves the bootstrap problem: "How can WordPress create a user if it doesn't have a user key yet?"

### Installation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  DURING PLUGIN ACTIVATION (one-time setup)                      │
│                                                                 │
│  1. WordPress plugin generates a random secret:                 │
│     PLUGIN_SECRET = "sk_plugin_" + random_base64(32)            │
│     e.g. "sk_plugin_Kx7mP9qR2wN5vB8cD3fG6hJ4kL1nM0pQ..."        │
│                                                                 │
│  2. Plugin displays secret to admin with instructions:          │
│     "Copy this to your backend .env file:"                      │
│     ACM2_PLUGIN_SECRET=sk_plugin_Kx7mP9qR2wN5vB8c...            │
│                                                                 │
│  3. Plugin stores secret in WordPress:                          │
│     update_option('acm2_plugin_secret', $secret);               │
│                                                                 │
│  4. Admin adds to backend .env:                                 │
│     ACM2_PLUGIN_SECRET=sk_plugin_Kx7mP9qR2wN5vB8c...            │
└─────────────────────────────────────────────────────────────────┘
```

### How It's Used

```python
# Backend: middleware.py or users.py route

from app.core.config import settings

async def create_user_endpoint(request: Request, ...):
    # Validate plugin secret
    plugin_secret = request.headers.get("X-ACM2-Plugin-Secret")
    if not plugin_secret or plugin_secret != settings.ACM2_PLUGIN_SECRET:
        raise HTTPException(status_code=401, detail="Invalid plugin secret")
    
    # Proceed with user creation...
```

---

## Encrypted Key Storage in WordPress

User API keys should be encrypted at rest in frontend.master MySQL.

### Encryption Approach

Use WordPress's `AUTH_KEY` from `wp-config.php` as the encryption key:

```php
// In WordPress plugin

class ACM2_Key_Encryption {
    
    /**
     * Encrypt an API key for storage
     */
    public static function encrypt($raw_key) {
        $key = hash('sha256', AUTH_KEY, true);  // 32-byte key from wp-config
        $iv = random_bytes(16);
        $encrypted = openssl_encrypt($raw_key, 'aes-256-cbc', $key, 0, $iv);
        return base64_encode($iv . $encrypted);  // IV prepended for decryption
    }
    
    /**
     * Decrypt an API key for use
     */
    public static function decrypt($encrypted_key) {
        $key = hash('sha256', AUTH_KEY, true);
        $data = base64_decode($encrypted_key);
        $iv = substr($data, 0, 16);
        $encrypted = substr($data, 16);
        return openssl_decrypt($encrypted, 'aes-256-cbc', $key, 0, $iv);
    }
}

// When storing (after user creation):
$encrypted = ACM2_Key_Encryption::encrypt($raw_api_key);
update_user_meta($user_id, 'acm2_api_key_enc', $encrypted);

// When retrieving (for React):
$encrypted = get_user_meta($user_id, 'acm2_api_key_enc', true);
$raw_key = ACM2_Key_Encryption::decrypt($encrypted);
```

### Why This Works

- `AUTH_KEY` is unique per WordPress install (generated during setup)
- Even if database is stolen, attacker needs `wp-config.php` to decrypt
- Standard AES-256-CBC encryption
- IV is random per key, stored alongside ciphertext

---

## master.db Schema

```sql
-- Users table: minimal info, just for linking
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wordpress_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API keys table: maps key_hash → user_id
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_users_wordpress ON users(wordpress_user_id);
```

---

## Authentication Flow

```
1. Request arrives with X-ACM2-API-Key: acm2_abc123...

2. Backend extracts prefix (first 12 chars): "acm2_abc123d"

3. Query master.db:
   SELECT key_hash, user_id FROM api_keys 
   WHERE key_prefix = "acm2_abc123d" AND revoked_at IS NULL

4. Validate bcrypt hash against full key

5. Get user_id (e.g., 6)

6. Open data/user_6.db for request processing
```

---

## User Creation Flow

```
1. WordPress calls POST /api/v1/users
   Headers: X-ACM2-Plugin-Secret: sk_plugin_Kx7mP9qR...
   Body: { username, email, wordpress_user_id: 6 }

2. Backend:
   a. Validate X-ACM2-Plugin-Secret against .env value
   b. Insert into master.db users table
   c. Generate API key: "acm2_" + random_base64(32)
   d. Extract prefix (first 8 chars after "acm2_")
   e. Hash full key with bcrypt
   f. Insert prefix + hash into master.db api_keys table
   g. Create user_6.db with schema
   h. Return plaintext key to WordPress (ONLY TIME IT'S RETURNED!)

3. WordPress:
   a. Encrypt returned key with AUTH_KEY
   b. Store encrypted key in wp_usermeta: acm2_api_key_enc
```

---

## Files to Modify

### 1. `acm2/app/db/master.py`

**Current**: Uses `aiomysql` to connect to remote MySQL  
**Change to**: Use `aiosqlite` to open local `data/master.db`

Key changes:
- Replace `aiomysql` imports with `aiosqlite`
- Change connection to open local file
- Convert MySQL syntax to SQLite syntax
- Add auto-initialization on startup

### 2. `acm2/app/auth/middleware.py`

**Current**: Calls `master.py` which tries MySQL  
**Change**: No change needed - it already calls master.py, which will now use SQLite

### 3. `acm2/app/api/routes/users.py`

**Current**: Creates user in master DB  
**Change**: No change needed - it already calls master.py

---

## Implementation

### Step 1: Rewrite master.py

Replace the entire `MasterDB` class to use aiosqlite:

```python
"""
Master Database Manager (SQLite)
Handles user accounts and API key lookups.
Local to backend - no network connection needed.
"""
import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Path to master database
MASTER_DB_PATH = Path(__file__).parent.parent.parent / "data" / "master.db"


class MasterDB:
    """Manages master database with user accounts and API keys."""
    
    def __init__(self):
        self._initialized = False
    
    async def _get_connection(self) -> aiosqlite.Connection:
        """Get database connection, initializing if needed."""
        MASTER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(MASTER_DB_PATH)
        conn.row_factory = aiosqlite.Row
        
        if not self._initialized:
            await self._init_schema(conn)
            self._initialized = True
        
        return conn
    
    async def _init_schema(self, conn: aiosqlite.Connection):
        """Create tables if they don't exist."""
        await conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wordpress_user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                revoked_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
            CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
            CREATE INDEX IF NOT EXISTS idx_users_wordpress ON users(wordpress_user_id);
        ''')
        await conn.commit()
        logger.info("Master database initialized")
    
    async def create_user(self, username: str, email: str,
                         wordpress_user_id: int) -> int:
        """Create a new user. Returns user ID."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO users (username, email, wordpress_user_id) VALUES (?, ?, ?)",
                (username, email, wordpress_user_id)
            )
            await conn.commit()
            user_id = cursor.lastrowid
            logger.info(f"Created user: {username} (ID: {user_id})")
            return user_id
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def get_user_by_wordpress_id(self, wp_id: int) -> Optional[Dict[str, Any]]:
        """Get user by WordPress user ID."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE wordpress_user_id = ?", (wp_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def create_api_key(self, user_id: int, key_hash: str,
                            key_prefix: str, name: str = None) -> int:
        """Create API key. Returns key ID."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO api_keys (user_id, key_hash, key_prefix, name) VALUES (?, ?, ?, ?)",
                (user_id, key_hash, key_prefix, name)
            )
            await conn.commit()
            return cursor.lastrowid
    
    async def get_user_by_key_prefix(self, key_prefix: str) -> Optional[tuple]:
        """Get (key_hash, user_id) by key prefix for auth."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                "SELECT key_hash, user_id FROM api_keys WHERE key_prefix = ? AND revoked_at IS NULL",
                (key_prefix,)
            )
            return await cursor.fetchone()
    
    async def get_user_by_api_key_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Get user info by API key hash."""
        async with await self._get_connection() as conn:
            cursor = await conn.execute(
                """SELECT u.* FROM users u
                   JOIN api_keys k ON u.id = k.user_id
                   WHERE k.key_hash = ?""",
                (key_hash,)
            )
            row = await cursor.fetchone()
            if row:
                # Update last_used_at
                await conn.execute(
                    "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                    (datetime.utcnow(), key_hash)
                )
                await conn.commit()
            return dict(row) if row else None
    
    async def revoke_api_key(self, key_id: int):
        """Revoke an API key."""
        async with await self._get_connection() as conn:
            await conn.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ?",
                (datetime.utcnow(), key_id)
            )
            await conn.commit()


# Singleton instance
_master_db: Optional[MasterDB] = None


async def get_master_db() -> MasterDB:
    """Get the master database instance."""
    global _master_db
    if _master_db is None:
        _master_db = MasterDB()
    return _master_db
```

### Step 2: Update middleware.py (minimal change)

The current middleware already calls `get_master_db()`. Just ensure it handles the SQLite response format. The main auth logic should work as-is since the method signatures are the same.

### Step 3: Remove MySQL dependencies

From `requirements.txt` or `pyproject.toml`:
- Remove `aiomysql` (if not used elsewhere)
- Ensure `aiosqlite` is present (should be, used by per-user DBs)

### Step 4: Remove MySQL env vars

From `.env`, remove:
```
MASTER_DB_HOST=...
MASTER_DB_USER=...
MASTER_DB_PASSWORD=...
MASTER_DB_NAME=...
```

---

## Frontend Changes

### WordPress Plugin Changes

1. **Plugin Activation**: Generate and display `ACM2_PLUGIN_SECRET` for admin to copy to backend `.env`

2. **User Creation**: Include `X-ACM2-Plugin-Secret` header when calling `POST /api/v1/users`

3. **Key Storage**: Encrypt API key before storing in `wp_usermeta`:
   ```php
   $encrypted = ACM2_Key_Encryption::encrypt($raw_api_key);
   update_user_meta($user_id, 'acm2_api_key_enc', $encrypted);
   ```

4. **Key Retrieval**: Decrypt when passing to React:
   ```php
   $encrypted = get_user_meta($user_id, 'acm2_api_key_enc', true);
   $raw_key = ACM2_Key_Encryption::decrypt($encrypted);
   // Pass $raw_key to React via localized script data
   ```

### React Changes

**None required.** React still receives the raw key (decrypted by WordPress) and sends it in `X-ACM2-API-Key` header as before.

---

## Testing

1. Delete any existing `data/master.db` (fresh start)
2. Restart backend
3. Call `POST /api/v1/users` to create a test user
4. Check `data/master.db` has user and api_key rows
5. Use returned key in `X-ACM2-API-Key` header
6. Verify authentication works

---

## Verification Checklist

### Backend
- [ ] `ACM2_PLUGIN_SECRET` added to `.env`
- [ ] `data/master.db` created on first request
- [ ] `users` and `api_keys` tables exist
- [ ] User creation rejects requests without valid plugin secret
- [ ] User creation inserts into both tables
- [ ] Auth looks up key by prefix
- [ ] Auth validates bcrypt hash
- [ ] Auth returns correct user_id
- [ ] Per-user database opens correctly
- [ ] No MySQL connection errors (removed dependency)

### WordPress
- [ ] Plugin secret generated on activation
- [ ] Plugin secret stored in `wp_options`
- [ ] Plugin secret included in user creation requests
- [ ] API key encrypted before storage in `wp_usermeta`
- [ ] API key decrypted correctly when passing to React

---

## Summary

| Component | Before | After |
|-----------|--------|-------|
| Backend master.py | aiomysql to remote MySQL | aiosqlite to local data/master.db |
| User creation auth | None (open endpoint) | Plugin secret validation |
| WordPress key storage | Plaintext in wp_usermeta | Encrypted with AUTH_KEY |
| Network dependency | Backend connects to frontend MySQL | None - fully isolated |

**Frontend Changes**:
- Plugin activation: generate & display plugin secret
- User creation: include X-ACM2-Plugin-Secret header  
- Key storage: encrypt with AUTH_KEY before storing
- Key retrieval: decrypt before passing to React

**Backend Changes**:
- Rewrite master.py to use SQLite
- Add plugin secret validation to user creation endpoint
- Add ACM2_PLUGIN_SECRET to .env

**Result**: 
- Backend is fully self-contained (no cross-network database)
- Two-layer security: plugin secret for user creation, user keys for API access
- Keys encrypted at rest in WordPress
