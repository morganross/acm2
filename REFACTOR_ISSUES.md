# Per-User Database Refactor - Issues Found

**Created:** January 10, 2026  
**Status:** ✅ ALL FIXED (January 10, 2026)

This document lists issues discovered during the code trace investigation of the per-user database refactor.

---

## Summary

| # | Issue | Severity | Fix Effort | Status |
|---|-------|----------|------------|--------|
| 1 | Double decryption in key_injection | Low | 5 min | ✅ FIXED |
| 2 | Wrong dependency order in github_connections | Low | 10 min | ✅ FIXED |
| 3 | Unauthenticated endpoints (rate_limits, websocket) | Medium | 20 min | ✅ FIXED |
| 4 | Duplicate close() method in master.py | Trivial | 1 min | ✅ FIXED |
| 5 | Two DB systems - **Consolidate to SQLAlchemy** | Medium | 45 min | ✅ FIXED |
| 6 | Encryption singleton can't recover if started without key | Low | 10 min | ✅ FIXED |
| 7 | Missing user_id validation in repositories | Low | Document | ✅ DOCUMENTED |

---

## Issue 1: Double Decryption in key_injection.py

**File:** `acm2/app/security/key_injection.py` (lines 38-46)

**Problem:**  
The code first calls `manager.get_all_keys()` which decrypts all keys, then for each provider it calls `manager.get_key(provider)` which decrypts them again.

```python
# Current (buggy):
configured_providers = await manager.get_all_keys()  # Decrypts all keys

for provider in configured_providers:
    env_var = provider_to_env_var.get(provider)
    if env_var:
        key = await manager.get_key(provider)  # Decrypts AGAIN
        if key:
            env[env_var] = key
```

**Fix:**  
Use the already-decrypted keys from `get_all_keys()`:

```python
# Fixed:
decrypted_keys = await manager.get_all_keys()  # Returns {provider: decrypted_key}

for provider, key in decrypted_keys.items():
    env_var = provider_to_env_var.get(provider)
    if env_var and key:
        env[env_var] = key
```

**Impact:** Performance (unnecessary crypto operations). Not a security issue.

---

## Issue 2: Wrong Dependency Order in github_connections.py

**File:** `acm2/app/api/routes/github_connections.py` (all endpoints)

**Problem:**  
All 9 endpoints in this file have dependencies in wrong order:

```python
# Current (suboptimal):
async def some_endpoint(
    db: AsyncSession = Depends(get_user_db),      # FIRST
    user: Dict[str, Any] = Depends(get_current_user),  # SECOND
):
```

But `get_user_db` internally calls `get_current_user` to get the user_id. So authentication happens twice per request.

**Fix:**  
Swap the order so `get_current_user` runs first:

```python
# Fixed:
async def some_endpoint(
    user: Dict[str, Any] = Depends(get_current_user),  # FIRST
    db: AsyncSession = Depends(get_user_db),           # SECOND
):
```

**Impact:** Redundant authentication calls. Not a security issue but wasteful.

---

## Issue 3: Unauthenticated Endpoints

**Files:**
- `acm2/app/api/routes/models.py` - No auth on GET /models, GET /models/pricing
- `acm2/app/api/routes/rate_limits.py` - No auth on any rate limit endpoints
- `acm2/app/api/routes/runs/websocket.py` - WebSocket accepts without auth

**Problem:**

| Endpoint | Risk |
|----------|------|
| `GET /models` | Low - read-only config, probably intentional |
| `GET /models/pricing` | Low - public pricing data |
| `GET /rate-limits` | Medium - exposes system config |
| `PUT /rate-limits/{provider}` | High - allows modifying limits |
| `WS /runs/ws/run/{run_id}` | Medium - anyone can subscribe to run updates |

**Fix Options:**

1. **models.py** - Leave public (intentional)
2. **rate_limits.py** - Add `user: dict = Depends(get_current_user)` to all endpoints
3. **websocket.py** - Authenticate before accepting WebSocket connection

**Impact:** Security - unauthorized access to rate limit controls and run progress.

---

## Issue 4: Duplicate close() Method in master.py

**File:** `acm2/app/db/master.py` (lines 43-53)

**Problem:**  
The `close()` method is defined twice in the `MasterDB` class:

```python
async def close(self):
    """Close connection pool."""
    if self._pool:
        self._pool.close()
        await self._pool.wait_closed()
        logger.info("Master database pool closed")

async def close(self):  # <-- Duplicate!
    """Close connection pool."""
    if self._pool:
        self._pool.close()
        await self._pool.wait_closed()
        logger.info("Master database pool closed")
```

Python silently uses the second definition. First one is dead code.

**Fix:** Delete one of them.

**Impact:** None (dead code). Trivial cleanup.

---

## Issue 5: Two Separate Database Systems - CONSOLIDATE TO SQLALCHEMY

**Decision:** Use SQLAlchemy exclusively (easier future migration to PostgreSQL/MySQL)

**Files to modify:**
- `acm2/app/db/user_db.py` - Remove or repurpose
- `acm2/app/db/user_schema.sql` - Delete
- `acm2/app/infra/db/models/` - Add new models
- `acm2/app/security/provider_keys.py` - Switch to SQLAlchemy

**Problem:**  
Two different systems write to the same per-user SQLite file (`data/user_{id}.db`):

| System | Creates Tables | Used For |
|--------|---------------|----------|
| aiosqlite (`UserDB`) | runs, provider_keys, usage_stats | Provider key storage |
| SQLAlchemy | presets, runs, documents, contents, artifacts, github_connections | Everything else |

The `runs` table schema differs between systems:
- aiosqlite version: `system_prompt`, `user_prompt`, `model_ids`, `criteria`
- SQLAlchemy version: `phase`, `results_summary`, `run_config`, etc.

**Current State:**  
This works because:
- Provider keys use `UserDB` (aiosqlite)
- Everything else uses SQLAlchemy
- They don't conflict because they use different tables (mostly)

**Risk:**  
The duplicate `runs` table definition could cause issues if both systems try to use it.

**Fix Plan:**

1. **Create SQLAlchemy models:**
   - `ProviderKey` model in `acm2/app/infra/db/models/provider_key.py`
   - `UsageStats` model in `acm2/app/infra/db/models/usage_stats.py`

2. **Create repository:**
   - `ProviderKeyRepository` in `acm2/app/infra/db/repositories/provider_key.py`

3. **Update ProviderKeyManager:**
   - Change from using `UserDB` (aiosqlite) to `ProviderKeyRepository` (SQLAlchemy)
   - Pass SQLAlchemy session instead of user_id

4. **Update callers:**
   - `key_injection.py` - Pass session to ProviderKeyManager
   - `provider_keys.py` routes - Already have session from `get_user_db`

5. **Cleanup:**
   - Delete `user_schema.sql`
   - Remove runs/usage_stats code from `user_db.py` (or delete entire file)
   - Keep `get_user_db()` function name but have it return SQLAlchemy session

---

## Issue 6: Encryption Singleton Can't Recover

**File:** `acm2/app/security/encryption.py` (lines 117-125)

**Problem:**  
The `get_encryption_service()` function creates a singleton:

```python
_encryption_service: Optional[EncryptionService] = None

def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()  # Reads ENCRYPTION_KEY once
    return _encryption_service
```

If `EncryptionService` is created before `.env` is loaded (or before `ENCRYPTION_KEY` is set), it initializes with `fernet = None` and stays that way forever.

**Fix Options:**

1. **Lazy retry** - If `fernet is None`, try loading key again on each call
2. **Fail loudly at startup** - Make app crash if key missing (your stated preference)
3. **Reset singleton** - Add a `reset_encryption_service()` for testing

**Recommended Fix (fail loudly):**

```python
def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
        if _encryption_service.fernet is None:
            raise RuntimeError("ENCRYPTION_KEY not configured - cannot start")
    return _encryption_service
```

**Impact:** Server may start in broken state if key timing is wrong.

---

## Issue 7: Missing user_id Validation in Repositories

**Files:** All repository classes in `acm2/app/infra/db/repositories/`

**Problem:**  
When routes call repositories like:

```python
repo = RunRepository(session, user_id=user['id'])
run = await repo.get_by_id(run_id)
```

The repository doesn't verify that `run.user_id == user_id`. It trusts that:
1. The session is connected to the correct per-user database
2. The `user` dict came from valid authentication

**Current Protection:**  
This is mitigated because:
- `get_user_db` connects to `data/user_{id}.db` based on authenticated user
- Each user has their own database file
- There's no cross-user data in the per-user database

**Risk:**  
If a bug allowed wrong session/user pairing, data could leak. Defense-in-depth would add explicit checks.

**Recommendation:**  
Low priority. Consider adding `WHERE user_id = :user_id` to queries for extra safety, but current architecture already provides isolation.

---

## Fix Priority

**Phase 1 - Quick Wins (15 min total):**
- [x] Issue 1: Fix double decryption ✅
- [x] Issue 4: Remove duplicate close() ✅

**Phase 2 - Dependency Order (10 min):**
- [x] Issue 2: Fix dependency order in github_connections (9 endpoints fixed) ✅

**Phase 3 - Security (30 min):**
- [x] Issue 3: Add auth to rate_limits.py (3 endpoints) ✅
- [x] Issue 3: Add auth to websocket.py (token query param) ✅

**Phase 4 - SQLAlchemy Consolidation (45 min):**
- [x] Issue 5: Create ProviderKey SQLAlchemy model ✅
- [x] Issue 5: Create UsageStats SQLAlchemy model ✅
- [x] Issue 5: Create ProviderKeyRepository ✅
- [x] Issue 5: Create UsageStatsRepository ✅
- [x] Issue 5: Update ProviderKeyManager to use SQLAlchemy ✅
- [x] Issue 5: Update key_injection.py with auto-session helpers ✅
- [x] Issue 5: Update FPF and GPTR adapters ✅

**Phase 5 - Robustness (10 min):**
- [x] Issue 6: Make encryption fail loudly at startup ✅

**Phase 6 - Document:**
- [x] Issue 7: Add detailed comment explaining user_id isolation in session.py ✅

---

## Files Modified

### New Files Created:
- `acm2/app/infra/db/models/provider_key.py` - ProviderKey SQLAlchemy model
- `acm2/app/infra/db/models/usage_stats.py` - UsageStats SQLAlchemy model
- `acm2/app/infra/db/repositories/provider_key.py` - ProviderKeyRepository
- `acm2/app/infra/db/repositories/usage_stats.py` - UsageStatsRepository

### Files Modified:
- `acm2/app/security/key_injection.py` - Refactored to use SQLAlchemy, added auto-session helpers
- `acm2/app/security/provider_keys.py` - Switched from aiosqlite UserDB to SQLAlchemy
- `acm2/app/security/encryption.py` - Added fail-loud startup check
- `acm2/app/api/routes/github_connections.py` - Fixed dependency order (9 endpoints)
- `acm2/app/api/routes/rate_limits.py` - Added authentication (3 endpoints)
- `acm2/app/api/routes/runs/websocket.py` - Added WebSocket authentication
- `acm2/app/db/master.py` - Removed duplicate close() method
- `acm2/app/infra/db/session.py` - Added security documentation
- `acm2/app/infra/db/models/__init__.py` - Exported new models
- `acm2/app/infra/db/repositories/__init__.py` - Exported new repositories
- `acm2/app/adapters/fpf/adapter.py` - Updated to use auto-session helper
- `acm2/app/adapters/gptr/adapter.py` - Updated to use auto-session helper
