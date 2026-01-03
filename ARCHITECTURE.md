# ACM2 Production Architecture

## Overview

The application uses a dual-auth architecture:
- **Web Users**: WordPress sessions (handled by WordPress)
- **API Users**: API keys (standalone access)

Both auth methods map to the same user account and access the same per-user database.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB USERS                                │
│                                                                  │
│   Browser → WordPress (sessions) → React Frontend → API         │
│                                      (session cookie auth)       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         API USERS                                │
│                                                                  │
│   Their Code (Python/JS/curl) → API (API key auth)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### WordPress (Apache)
- Handles: User registration, login, password reset, payments
- Generates: Session tokens for authenticated users
- Location: `yoursite.com`

### React Frontend
- Served by: Uvicorn (or CDN in production)
- Auth: Uses WordPress session cookie
- Location: `app.yoursite.com` or embedded in WordPress

### FastAPI Backend (Uvicorn)
- Handles: All application logic
- Auth: Accepts both session cookies AND API keys
- Location: `api.yoursite.com` or `yoursite.com/api`

---

## Authentication Flow

### Web Users (Session-Based)
```
1. User logs into WordPress
2. WordPress creates session: { session_id: "abc123", user_id: 42 }
3. WordPress sets cookie: session_id=abc123
4. User accesses React app
5. React makes API calls with cookie automatically included
6. API validates session with WordPress → identifies user
7. API connects to user's database file
```

### API Users (API Key-Based)
```
1. User generates API key in WordPress dashboard
2. Key is stored (hashed) in master database
3. User includes key in requests: Authorization: Bearer <api_key>
4. API validates key → identifies user
5. API connects to user's database file
```

---

## Database Architecture

### Per-User Database Isolation
```
/data/
  master.db           ← User accounts, API keys, billing
  user_123.db         ← Alice's application data
  user_456.db         ← Bob's application data
  user_789.db         ← Carol's application data
```

### Benefits
- **True isolation**: No risk of data leaking between users
- **Easy backups**: Export one user's data by copying their file
- **Easy deletion**: Delete user = delete their file
- **Performance**: Each database stays small
- **Compliance**: Easier for GDPR, data residency requirements

### Master Database Schema
```sql
users (
  id,
  wordpress_user_id,
  database_file,
  created_at
)

api_keys (
  id,
  user_id,
  key_hash,
  name,
  created_at,
  last_used_at,
  revoked_at
)
```

---

## Server Architecture

### Development
```
Uvicorn (single process, --reload) → FastAPI → SQLite
```

### Production
```
Uvicorn (multiple workers) → FastAPI → SQLite per user
```

### Production with Scale
```
Load Balancer → Multiple Uvicorn instances → Shared storage for SQLite files
```

### Optional: Add Nginx
Only needed if you want:
- SSL termination (or use Cloudflare instead)
- Static file serving (or use CDN)
- Rate limiting at edge
- Multiple apps on one server

---

## Hosting Setup

### Option 1: Subdomain Split
```
yoursite.com          →  WordPress (Apache)
app.yoursite.com      →  React frontend (Uvicorn or CDN)
api.yoursite.com      →  FastAPI (Uvicorn)
```

### Option 2: Path-Based (Apache Proxy)
```
yoursite.com/*        →  WordPress
yoursite.com/app/*    →  Proxy to Uvicorn (frontend)
yoursite.com/api/*    →  Proxy to Uvicorn (API)
```

---

## Security Considerations

### Session Security
- Sessions stored server-side (WordPress)
- Cookie is HTTP-only, Secure, SameSite
- Session expires after inactivity

### API Key Security
- Keys stored hashed (bcrypt/argon2)
- Keys can be revoked
- Rate limiting per key
- Keys never logged

### Database Security
- Each user's database is a separate file
- User can only access their own database
- API validates user before connecting to their database

---

## API Auth Implementation

FastAPI will accept both auth methods:

```python
async def get_current_user(request: Request):
    # Check for API key first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
        user = await validate_api_key(api_key)
        if user:
            return user
    
    # Fall back to session cookie
    session_id = request.cookies.get("session_id")
    if session_id:
        user = await validate_wordpress_session(session_id)
        if user:
            return user
    
    raise HTTPException(401, "Not authenticated")
```

---

## Migration Path

### Current State
- Single database, no auth
- Uvicorn serving everything

### Phase 1: Add User Isolation
- Implement per-user database files
- Add user context to all queries

### Phase 2: Add WordPress Integration
- Set up JWT/session handoff from WordPress
- Add session validation middleware

### Phase 3: Add API Keys
- API key generation in WordPress dashboard
- API key validation in FastAPI

### Phase 4: Production Deployment
- Uvicorn with multiple workers
- Proper domain/subdomain setup
- SSL via Cloudflare or Let's Encrypt

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Web Server | Uvicorn (ASGI) |
| API Framework | FastAPI |
| Frontend | React + TypeScript + Vite |
| Database | SQLite (per-user files) |
| Auth (Web) | WordPress Sessions |
| Auth (API) | API Keys |
| CMS/Users | WordPress |
| Payments | WordPress plugin (WooCommerce, etc.) |

---

## Why This Architecture?

| Benefit | Reason |
|---------|--------|
| **Security** | No API keys exposed in browser |
| **Simplicity** | WordPress handles login, password reset, etc. |
| **Flexibility** | Power users can script against your API |
| **Separation** | API is a standalone product, frontend is just one client |
| **Isolation** | Per-user databases for true data separation |
| **Scalability** | Can scale horizontally with load balancer |
