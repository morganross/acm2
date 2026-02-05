# ACM2 - API Cost Multiplier v2

Multi-LLM research evaluation and orchestration platform with per-user data isolation.

## Architecture Overview

ACM2 is a two-server architecture:

```
┌─────────────────────────┐      ┌─────────────────────────┐
│   FRONTEND SERVER       │      │   BACKEND SERVER        │
│   (WordPress/Bitnami)   │      │   (FastAPI/Python)      │
│                         │      │                         │
│   16.145.206.59         │◄────►│   54.71.183.56          │
│   Apache + PHP          │      │   Uvicorn + Python 3.11 │
│   React UI (built)      │      │   SQLite per-user DBs   │
│                         │      │                         │
│   Plugin repo:          │      │   Main repo:            │
│   acm-wordpress-plugin  │      │   acm2                  │
└─────────────────────────┘      └─────────────────────────┘
```

### Key Features

- **Per-user database isolation**: Each user gets their own SQLite database (`user_{id}.db`)
- **O(1) user lookup**: API keys contain embedded user ID (`acm2_u{user_id}_{random}`)
- **No master database**: Eliminated single shared database bottleneck
- **WordPress integration**: Users authenticate via WordPress, API keys managed transparently
- **Multi-LLM orchestration**: Run prompts against multiple LLM providers simultaneously

---

## Servers

### Backend Server (54.71.183.56)

- **Purpose**: FastAPI backend, LLM orchestration, per-user databases
- **OS**: Windows Server (AWS Lightsail)
- **Stack**: Python 3.11, FastAPI, Uvicorn, SQLite
- **Port**: 80
- **Repo**: `C:\devlop\acm2` (this repo)
- **Data**: `C:\devlop\acm2\acm2\data\user_{id}.db`

### Frontend Server (16.145.206.59)

- **Purpose**: WordPress site, user authentication, React UI hosting
- **OS**: Linux (Bitnami WordPress on AWS Lightsail)
- **Stack**: Apache, PHP, WordPress, React (pre-built)
- **User**: `bitnami` (for file operations)
- **Plugin path**: `/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/`
- **Repo**: `acm-wordpress-plugin` (separate GitHub repo)

---

## Development Setup

### Prerequisites

- VS Code with Remote Tunnels extension
- SSH access to frontend server
- Python 3.11+ on backend server
- Node.js 18+ (for React UI builds)

### Backend Development (VS Code Tunnel)

The backend server runs a VS Code tunnel, allowing remote development:

```powershell
# On backend server, VS Code tunnel is running
# Connect via: VS Code > Remote Explorer > Tunnels
```

The AI/LLM assistant connects via this tunnel and has full access to:
- Terminal (PowerShell)
- File system
- Git operations

### Frontend Deployment (SSH from Backend)

The backend AI SSHs into the frontend to deploy changes:

```python
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Run commands on frontend
stdin, stdout, stderr = ssh.exec_command('cd /path && npm run build')
```

**Required credentials** (for initial setup):
- Frontend IP address
- SSH username and password
- Sudo access for `bitnami` user operations

---

## Authentication Flow

### API Key Format

```
acm2_u{user_id}_{random_string}
     │         │
     │         └── 22 random characters
     └── User ID (extracted for O(1) lookup)
```

Example: `acm2_u6_kKDHtSEDaGBC6MUbJSoEn`

### User Creation

1. WordPress user logs in
2. WordPress plugin calls `POST /api/v1/users` with `X-ACM2-Plugin-Secret` header
3. Backend creates `user_{id}.db` and returns API key
4. WordPress stores API key in user meta
5. React app receives API key via `window.acm2Config.apiKey`

### Request Authentication

1. React app includes `X-ACM2-API-Key: acm2_u{id}_{...}` header
2. Backend extracts user ID from key format
3. Backend connects to `user_{id}.db`
4. Request processed with user's isolated data

---

## Database Architecture

### Per-User Databases

Each user has their own SQLite file:
```
data/
├── user_1.db
├── user_2.db
├── user_6.db
└── user_7.db
```

### Tables (per user DB)

- `presets` - Saved configurations
- `contents` - Prompts, instructions, documents
- `runs` - Execution history
- `tasks` - Individual LLM tasks within runs
- `artifacts` - Generated outputs
- `provider_keys` - Encrypted LLM API keys
- `user_meta` - Seed status, preferences
- `user_settings` - User preferences

### Shared Database (Legacy)

Location: `C:\Users\Administrator\.acm2\acm2.db`

Used only for:
- Seed source for new users (Default Preset)
- Legacy compatibility

---

## Key Environment Variables

### Backend (`acm2/.env`)

```bash
# Plugin secret for user creation (permanent)
ACM2_PLUGIN_SECRET=sk_plugin_xxxxx

# Seed configuration
SEED_PRESET_ID=default
SEED_VERSION=1.0.0

# Database URL (shared DB for seeding)
DATABASE_URL=sqlite+aiosqlite:///C:/Users/Administrator/.acm2/acm2.db
```

### Frontend (WordPress)

Configured in plugin settings:
- Backend API URL
- Plugin secret (matches backend)

---

## React UI

### Location

- **Source**: `acm-wordpress-plugin/ui/` (TypeScript + Vite)
- **Build output**: `acm-wordpress-plugin/assets/react-build/assets/`

### Key Files

- `ui/src/api/client.ts` - API client with auth headers
- `ui/src/pages/Configure.tsx` - Preset configuration
- `ui/src/pages/Execute.tsx` - Run execution

### Building

```bash
# On frontend server
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui
npm install
npm run build
```

### API Client Configuration

The React app reads config from WordPress:

```typescript
// client.ts
const API_BASE_URL = window.acm2Config?.apiUrl || '/api/v1'

function getApiKey(): string | null {
  return window.acm2Config?.apiKey || localStorage.getItem('acm_api_key')
}

// All requests use X-ACM2-API-Key header
headers['X-ACM2-API-Key'] = getApiKey()
```

---

## Recent Refactors (January 2026)

### 1. Eliminated Master Database
- Removed `master.db` dependency
- User lookup now O(1) via embedded ID in API key
- Each user's data fully isolated

### 2. New API Key Format
- Old: `acm2_{random}` (required DB lookup)
- New: `acm2_u{user_id}_{random}` (instant user ID extraction)

### 3. Permanent Plugin Secret
- Plugin secret for user creation only
- API keys for all other operations
- Separation of concerns

### 4. React UI Recovery
- Full React UI was accidentally deleted (commit `5107384`)
- Recovered from git history
- Now lives in frontend repo, not backend

### 5. Auth Header Fix
- Changed from `Authorization: Bearer` to `X-ACM2-API-Key`
- Matches WordPress Provider Keys page pattern
- Reads from `window.acm2Config.apiKey`

---

## Common Operations

### Start Backend Server

```powershell
cd C:\devlop\acm2
.\restart.ps1            # Normal restart (keeps data)
.\restart.ps1 -Purge     # DESTRUCTIVE: Delete all user data
```

Server runs detached in a hidden window. Logs: `c:\devlop\acm2\server.log`

### Deploy React UI Changes

```python
# From backend, SSH to frontend and rebuild
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

commands = [
    f'sudo -u bitnami bash -c "cd {PLUGIN_DIR}/ui && npm run build"',
    f'sudo -u bitnami git -C {PLUGIN_DIR} add -A',
    f'sudo -u bitnami git -C {PLUGIN_DIR} commit -m "Build React UI"',
    f'sudo -u bitnami git -C {PLUGIN_DIR} push origin main',
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    print(stdout.read().decode())

ssh.close()
```

### Restart Frontend (WordPress/Bitnami)

**NOTE**: Frontend is on a SEPARATE server (35.88.196.59). Restart via SSH:

```bash
ssh ubuntu@35.88.196.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
```

Or in Python:
```python
ssh.exec_command('sudo /opt/bitnami/ctlscript.sh restart apache')
```

### Check Database Contents

```python
import sqlite3

# Check user's presets
conn = sqlite3.connect('C:/devlop/acm2/acm2/data/user_6.db')
cur = conn.cursor()
cur.execute("SELECT id, name FROM presets")
print(cur.fetchall())
conn.close()
```

---

## Troubleshooting

### "Failing to load presets" on /configure

1. Check browser console for 401 errors
2. Verify `window.acm2Config.apiKey` is set
3. Ensure React app uses `X-ACM2-API-Key` header (not `Authorization: Bearer`)
4. Hard refresh (Ctrl+Shift+R) to clear cached JS

### User database not created

1. Check plugin secret matches between WordPress and backend
2. Verify `POST /api/v1/users` includes `X-ACM2-Plugin-Secret` header
3. Check backend logs for creation errors

### SSH connection issues

```python
# Use backenddev user with password
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# For file operations, use sudo -u bitnami
ssh.exec_command('sudo -u bitnami <command>')
```

---

## Repository Structure

```
acm2/
├── acm2/                       # Main Python package
│   ├── app/
│   │   ├── api/routes/         # FastAPI endpoints
│   │   ├── auth/               # API key, user registry
│   │   ├── db/                 # Database operations
│   │   ├── infra/db/           # SQLAlchemy models
│   │   └── services/           # Business logic
│   ├── data/                   # Per-user databases
│   └── ui/                     # React source (synced to frontend)
├── FilePromptForge/            # FPF sub-module
├── restart.ps1                 # Unified server restart script (use -Purge for fresh install)
└── README.md                   # This file
```

---

## Git Repositories

| Repo | Purpose | Location |
|------|---------|----------|
| `acm2` | Backend + shared UI source | `C:\devlop\acm2` |
| `acm-wordpress-plugin` | Frontend WordPress plugin | Frontend server |

Both repos should have the React UI source in sync. When editing UI:
1. Edit in `acm2/acm2/ui/`
2. Copy to frontend via SSH
3. Build on frontend
4. Commit to both repos

---

## Security Notes

- Plugin secret is **never** sent to browser
- API keys stored in WordPress user meta (server-side)
- Provider LLM keys encrypted in per-user databases
- All API requests require valid `X-ACM2-API-Key` header
- User ID extracted from key, no database lookup needed

---

## Known Issues

### Default Preset Missing

The shared database (`acm2.db`) should contain a "Default Preset" for seeding new users, but it's currently empty. New users start with no presets.

**Workaround**: Users must create their first preset manually via the /configure page.

**Fix needed**: Populate the shared database with a default preset and associated content items.
