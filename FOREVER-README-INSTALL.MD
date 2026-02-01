# FOREVER README — Installation & Deployment (WordPress Plugin)
acm2 can be used self-hosted, or in combination with the wordpress plugin for multi-user.

ACM2 IS 2 REPO'S

ACM2 WORDPRESS-PLUGIN: 
-WORDPRESS/APACHE HOSTS THE FRONTEND REACT WEBSITE FILES (OUR BLUE APP) THAT THE npm BUILD PROESS MADE. THEY ARE A FOLDER INSIDE OF WORDPRESS. THIS IS A DEPLOYMENT ONLY REPO.

-ALSO NORMAL PLUGIN STUFF: CHANGES WORDPRESS TO DIRECTLY INTEREACT WITH acm API UPON STUFF LIKE USER CREATION, AND KEY PASSING FROM WEBSITE TO API.

-IT ALSO ALLOWS ACM TO PIGGY BACK ON WORDPRESS'S DB HOST FOR THE ACM MASTER USER DB

-IT HAS A WHOLE ENTIRE PROXY WRITTEN INSIDE OF IT TO FORWARD WEBSITE API TRAFFIC TO BACKEND? (EASIER FOR KEY INJECTION? MORE PORTABLE THAN CONFIGURING PROXY IN APACHE?)




ACM2:
-BACKEND PYTHON APP LOGIC SCRIPTS
-SQLite 
-THE ACM API SERVER
-WEBSOCKET SERVER

-ACM FRONTEND DEVELOPMENT FILES. THEY ARE BULT HERE AND SHIPPED TO THE FRONTEND SERVER FOLDER USING THE ACM-WORDPRESS-PLUGIN. NOT SERVED HERE (EXCEPT SELF-HOSTED).

**Backened install**

clone repo
install
    install dependancies for acm, fpf, react
    install dependancies for gpt-r
npm build and uvicorn serve the api and websockts


**Wordpress Plugin Build Process**

 React Build Output Location

The React build output must be written to the **active** WordPress install:

- **Vite outDir**:
  - `C:/xampp2/htdocs/wordpress/wp-content/plugins/acm2-integration/assets/react-build`

**Build command:**
- `npm run build` from `C:\dev\godzilla\ui`

push to plugin repo

**WordPress Plugin Installation**
clone plugin repo
1. Copy plugin folder to WordPress plugins directory:
   - `C:\xampp2\htdocs\wordpress\wp-content\plugins\acm2-integration\`
2. Activate the plugin in WordPress Admin → Plugins.
3. Confirm the ACM2 admin menu appears (Settings, Provider Keys, App).

---

---

## 4) WordPress Configuration

WordPress must be able to reach the ACM2 API at:
- `http://127.0.0.1:8000/api/v1`

configurable at line x in file y

The plugin exposes a REST proxy at:
- `/wordpress/wp-json/acm2/v1/*`

The plugin injects config into the page:
- `window.acm2Config.apiUrl = '/wordpress/wp-json/acm2/v1'`
- `window.acm2Config.nonce = <wp_rest_nonce>`


---

## 5) Required Database Tables

### 5.1 WordPress DB (acm2_wordpress)
Custom table created by plugin:
- `wp_acm2_api_keys`

**Schema:**
- `id` (bigint, auto increment, PK)
- `wp_user_id` (bigint, unique, required)
- `acm2_api_key` (varchar(255), required)
- `created_at` (datetime, default current timestamp)
- `updated_at` (datetime, auto update)

### 5.2 ACM2 Master DB (MySQL)
Database: `acm2_master`

**Tables:**
- `users` (id, username, email, wordpress_user_id, created_at, updated_at)
- `api_keys` (id, user_id, key_hash, key_prefix, name, last_used_at, created_at, revoked_at)

Schema file:
- `acm2/acm2/app/db/master_schema_mysql.sql`


























er-User SQLite
- Each user gets a DB at `data/user_<id>.db`
- Presets and runs are stored here


---

## 7) User Sync Flow

When a new WordPress user registers:
1. Plugin calls `POST /api/v1/users` on ACM2 backend
2. ACM2 creates the user and returns an API key
3. Plugin saves the API key to `wp_acm2_api_keys`

---

## 8) Verification Checklist

- WordPress login works
- ACM2 App loads in WordPress Admin
- `window.acm2Config` exists
- `/wordpress/wp-json/acm2/v1/presets` returns 200 with `X-WP-Nonce`
- Presets appear in dropdown

---

## 9) Common Failure Modes

1. **Old bundle loaded**
   - Build output pointing to wrong WordPress install
2. **401 Unauthorized**
   - Missing `X-WP-Nonce` header in frontend requests
3. **404 Not Found**
   - Missing backend endpoint or wrong API base URL

---

## 10) Absolute Rules

- **Do not modify presets in DB directly**
- **Do not change preset documents/models via SQL**
- The GUI is the only source of truth for presets

---

## 11) Quick Paths Reference

- WordPress root: `C:\xampp2\htdocs\wordpress\`
- Plugin root: `C:\xampp2\htdocs\wordpress\wp-content\plugins\acm2-integration\`
- React build output: `C:\xampp2\htdocs\wordpress\wp-content\plugins\acm2-integration\assets\react-build\`
- ACM2 backend: `C:\dev\godzilla\acm2\acm2\`

---

## 12) Notes

This file is meant to be permanent. Update it only when installation steps or required configs change.

---

## 13) Backend Installation & Architecture (ACM2)

### 13.1 Install Overview (What gets installed)

- The ACM2 backend is a Python app with FastAPI, DB layer, and generator adapters; dependencies are defined in the project metadata at [acm2/pyproject.toml](acm2/pyproject.toml#L1-L61).
- GPT‑Researcher (GPT‑R) is a required dependency and runs via an internal subprocess adapter; the adapter checks for the `gpt_researcher` package during health checks and executes a local entrypoint script for each task [app/adapters/gptr/adapter.py](app/adapters/gptr/adapter.py#L50-L79).
- FilePromptForge (FPF) is a separate tool co-located in the repo; the adapter expects the `FilePromptForge/` folder and a `.env` with provider keys [app/adapters/fpf/README.md](app/adapters/fpf/README.md#L90-L109).

### 13.2 Architecture as it relates to install

- **Core server**: FastAPI + Uvicorn with DB and background tasks (dependencies defined in [acm2/pyproject.toml](acm2/pyproject.toml#L1-L61)).
- **GPT‑R adapter**: Uses a subprocess to isolate GPT‑Researcher; input is passed via env vars and executed in [app/adapters/gptr/entrypoint.py](app/adapters/gptr/entrypoint.py#L10-L69).
- **FPF adapter**: Wraps FilePromptForge CLI and reads keys from the FilePromptForge `.env` per adapter requirements [app/adapters/fpf/README.md](app/adapters/fpf/README.md#L90-L126).

### 13.3 Concrete code touchpoints (install‑critical)

- Dependency list (Python >= 3.11, FastAPI stack, GPT‑Researcher, provider SDKs): [acm2/pyproject.toml](acm2/pyproject.toml#L1-L61)
- GPT‑R health check import (`gpt_researcher`) and subprocess runner: [app/adapters/gptr/adapter.py](app/adapters/gptr/adapter.py#L50-L79)
- GPT‑R entrypoint env vars (`GPTR_PROMPT`, `GPTR_REPORT_TYPE`, `GPTR_TONE`, `GPTR_SOURCE_URLS`) and GPTResearcher execution: [app/adapters/gptr/entrypoint.py](app/adapters/gptr/entrypoint.py#L10-L69)
- FPF adapter requirements and `.env` expectations: [app/adapters/fpf/README.md](app/adapters/fpf/README.md#L90-L126)

---

## 14) Proposal: Simple Fresh‑Windows Backend Installer (Plan)

### 14.1 Goals

- One‑command or one‑click setup for a clean Windows machine.
- Reproducible installs with pinned versions and consistent paths.
- Zero manual edits for environment variables or PATH setup.

### 14.2 Recommended approach (industry standard)

**Option A — PowerShell bootstrap script (preferred):**

- A signed PowerShell script that:
   - Installs Python 3.11+ (winget), Git, Node LTS.
   - Creates a venv, installs Python deps from `pyproject.toml`.
   - Installs npm deps and builds the UI.(files sent to wordpress plugin optionally)
   - Writes required environment variables and service configs.
   - Starts ACM2 as a Windows Service (NSSM or sc.exe with Python wrapper).

**Option B — Winget + Chocolatey wrapper:**

- Use winget for system tools; optional Chocolatey for NSSM.
- Scripted install with a single entrypoint (`install.ps1`).

### 14.3 Deliverables

- `scripts/install.ps1` — full backend install (idempotent).
- `scripts/verify.ps1` — environment and service health checks.
- `scripts/uninstall.ps1` — clean removal of services and venv.
- `services/acm2-service.ps1` — service runner wrapper.
- `docs/FRESH-WINDOWS-INSTALL.md` — step‑by‑step user guide.

### 14.4 Detailed plan (phased)

**Phase 1 — Environment bootstrap**
1. Check for admin privileges; if missing, re‑invoke elevated.
2. Install prerequisites (winget): Git, Python 3.11, Node LTS.
3. Validate versions and record to a local log.

**Phase 2 — Repo & Python setup**
1. Clone the repo to a standard path (default `C:\dev\godzilla`).
2. Create `.venv` and install Python deps (`pip install .`).
3. Validate `python -c "import gpt_researcher"` succeeds.

**Phase 3 — FPF + secrets setup**
1. Ensure `FilePromptForge/` exists.
2. Create `.env` template and validate required keys are present.
3. Validate FPF health check.

**Phase 4 — UI build**
1. Install npm deps.
2. Run `npm run build` to generate WordPress plugin assets.

**Phase 5 — Service install**
1. Register ACM2 API as a Windows service.
2. Configure service to set required env vars at launch.
3. Start service and verify port 8000 is listening.

**Phase 6 — Verification**
1. Health check endpoint returns 200.
2. Test GPT‑R and FPF adapters health checks.
3. Run minimal preset execution.

### 14.5 Best practices baked in

- Idempotent steps (safe re‑run).
- Clear logging to `C:\dev\godzilla\install.log`.
- No manual PATH edits; script handles all required PATH changes.
- Strict version pinning (Python + Node + npm).
- Service‑based backend (no manual terminal needed).

---

## 15) Cache Clearing — CRITICAL FOR DEVELOPMENT

### 15.1 The Problem

Caching has caused **3 years of "works once, never again" bugs**. The symptom:
- You change code
- You test it
- It works once
- You test again — it fails
- You stare at working code that doesn't run

**The cause**: Old cached versions of code are being executed while you look at new code.

### 15.2 The Solution: Cache Destruction Script

**Location**: `C:\dev\godzilla\clear_all_caches.ps1`

**Run this script:**
- AFTER every code change
- BEFORE every test
- NO EXCEPTIONS

```powershell
& "C:\dev\godzilla\clear_all_caches.ps1"
```

The script is **fully automatic** — no human interaction required. It clears all caches and restarts both Apache and ACM2.

### 15.3 What the Script Clears

| Step | Cache Type | Location | Why It Matters |
|------|------------|----------|----------------|
| 1 | Python `__pycache__` | `*/__pycache__/` | Compiled bytecode masks source changes |
| 2 | Python `.pyc` files | `*.pyc` | Loose compiled files |
| 3 | Vite/npm cache | `node_modules/.vite` | Old bundles served instead of new |
| 4 | WordPress transients | `wp_options` table | Cached API responses/settings |
| 5 | WordPress object cache | `wp-content/cache/` | File-based cache if enabled |
| 6 | SQLite WAL | `*.db-wal` | Uncommitted transactions |
| 7 | TypeScript build info | `*.tsbuildinfo` | Incremental build cache |
| 8 | Windows DNS cache | System | Stale DNS resolutions |
| 9 | ACM2 server | Port 8000 | Stops server to reload code |
| 10 | Apache | httpd.exe | **Clears PHP OPcache from memory** |
| 11 | ACM2 server | Port 8000 | Restarts with fresh code |

### 15.4 All 40 Cache Types (Complete Reference)

These are ALL the caches that can cause "works once, never again" bugs:

**Browser-Side Caches:**
1. HTTP Response Cache (Cache-Control headers)
2. Browser Memory Cache (in-memory JS/CSS)
3. Service Worker Cache (if installed)
4. Local Storage (localStorage API)
5. Session Storage (sessionStorage API)
6. IndexedDB (browser database)
7. Browser DNS Cache (chrome://net-internals/#dns)
8. HSTS Cache (security policy cache)
9. Favicon Cache (site icons)
10. Font Cache (web fonts)

**JavaScript/React Caches:**
11. React Query Cache (API response memoization)
12. React State (useState/useReducer)
13. React Context Cache
14. Zustand/Redux Store
15. SWR Cache (if using SWR)
16. Axios Interceptor Cache
17. fetch() Response Cache

**Build Tool Caches:**
18. Vite Cache (`node_modules/.vite`)
19. npm Cache (`~/.npm/_cacache`)
20. TypeScript Incremental Build (`.tsbuildinfo`)
21. ESLint Cache (`.eslintcache`)
22. Babel Cache (`node_modules/.cache/babel-loader`)

**PHP/WordPress Caches:**
23. PHP OPcache (compiled bytecode in memory) — **CRITICAL**
24. PHP Realpath Cache (file path resolution)
25. WordPress Transients (database cache)
26. WordPress Object Cache (file or Redis)
27. WordPress Autoload Cache (class loading)
28. Plugin-specific Caches (various plugins)

**Python Caches:**
29. `__pycache__` directories (compiled bytecode)
30. `.pyc` files (compiled Python)
31. pip Cache (`~/.cache/pip`)
32. Python import cache (`sys.modules`)
33. SQLAlchemy Connection Pool
34. SQLAlchemy Query Cache (if enabled)

**Database Caches:**
35. SQLite WAL (write-ahead log)
36. SQLite Page Cache
37. MySQL Query Cache (deprecated but may exist)
38. MySQL Buffer Pool

**System Caches:**
39. Windows DNS Cache
40. Windows File System Cache

### 15.5 No-Cache Headers Added to Code

The following code changes were made to prevent caching at the HTTP level:

**FastAPI Backend (`app/main.py`):**
```python
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
        response.headers["X-Accel-Expires"] = "0"  # nginx
        response.headers["Surrogate-Control"] = "no-store"  # CDNs
        return response

app.add_middleware(NoCacheMiddleware)
```

**WordPress Plugin (`acm2-integration.php`):**
```php
function acm2_disable_browser_caching() {
    if (strpos($_SERVER['REQUEST_URI'], 'acm2') !== false) {
        header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
        header('Pragma: no-cache');
        header('Expires: Thu, 01 Jan 1970 00:00:00 GMT');
    }
}
add_action('admin_init', 'acm2_disable_browser_caching');

function acm2_disable_rest_caching($response) {
    $response->header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0');
    $response->header('Pragma', 'no-cache');
    $response->header('Expires', 'Thu, 01 Jan 1970 00:00:00 GMT');
    return $response;
}
add_filter('rest_post_dispatch', 'acm2_disable_rest_caching');
```

**Vite Config (`vite.config.ts`):**
```typescript
export default defineConfig({
  cacheDir: '.vite_temp',
  server: {
    headers: {
      'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  },
})
```

**React App Enqueue (`class-react-app.php`):**
```php
// Cache buster using timestamp to guarantee no caching
$cache_bust = time();
wp_enqueue_script('acm2-react-app', $url, [], filemtime($file) . '.' . $cache_bust, true);
```

### 15.6 Why This Matters

Without aggressive cache clearing:
- You change `main.py` line 50
- Python runs the OLD compiled bytecode from `__pycache__`
- Your fix doesn't execute
- You think your fix is wrong
- You revert it or change it again
- Eventually the cache expires or you restart
- The fix works
- You try to reproduce
- The old cache is back
- "Works once, never again"

**The script prevents this by nuking ALL caches on every run.**

---

## 16) New Architecture: Frontend in Plugin Repo (January 2026)

### 16.1 Problem with Old Setup

- Frontend source lived in backend repo (`C:\dev\godzilla\ui`)
- After `npm run build`, built files had to be copied to WordPress plugin
- With 2 cloud nodes (backend + WordPress), this meant transferring files across network after every build

### 16.2 New Setup: Build in Place

Frontend source now lives in the plugin repo itself. Build outputs directly into the plugin's assets folder.

**Plugin repo structure:**
```
acm2-wordpress-plugin/
  plugin/                       ← WordPress uses this folder
    acm2-integration.php
    includes/
      class-api-proxy.php
      class-user-sync.php
      class-react-app.php
    admin/
    assets/
      react-build/              ← Build output goes here
        index.js
        index.css
  
  ui-src/                       ← React source (for rebuilding)
    src/
    package.json
    package-lock.json
    vite.config.ts              ← outDir: '../plugin/assets/react-build'
    tsconfig.json
    tailwind.config.js
    postcss.config.js
    components.json
    index.html
    node_modules/               ← .gitignored, NOT committed
```

### 16.3 What's in Git vs What's Local-Only

| In Git (committed) | Local only (.gitignored) |
|--------------------|--------------------------|
| `ui-src/src/` | `ui-src/node_modules/` |
| `ui-src/package.json` | |
| `ui-src/package-lock.json` | |
| `ui-src/vite.config.ts` | |
| `ui-src/*.json`, `*.js` configs | |
| `plugin/assets/react-build/*` | |

### 16.4 Development Workflow (WordPress Node)

```bash
cd /path/to/wp-content/plugins/acm2-wordpress-plugin/ui-src
npm install          # Downloads node_modules (one-time, or after package.json changes)
npm run build        # Outputs to ../plugin/assets/react-build/
```

### 16.5 Production Deployment

Option A: Clone and use pre-built assets
```bash
git clone https://github.com/you/acm2-wordpress-plugin.git
# Built assets already in plugin/assets/react-build/ — ready to use
```

Option B: Clone and rebuild
```bash
git clone https://github.com/you/acm2-wordpress-plugin.git
cd acm2-wordpress-plugin/ui-src
npm install
npm run build
```

### 16.6 Backend Repo Changes

The `ui/` folder is removed from the backend repo (`acm2`). Backend repo now contains only:
- Python FastAPI app
- FPF / GPTR adapters
- SQLite databases
- CLI tools

### 16.7 Vite Config Change

Update `ui-src/vite.config.ts` to output to plugin folder:

```typescript
export default defineConfig({
  build: {
    outDir: '../plugin/assets/react-build',
    emptyDirBeforeWrite: true,
  },
  // ... rest of config
})
```

### 16.8 Summary

| Component | Repo | Node |
|-----------|------|------|
| Python backend, API, FPF, GPTR | `acm2` | Backend server |
| WordPress plugin PHP | `acm2-wordpress-plugin` | WordPress server |
| React source | `acm2-wordpress-plugin/ui-src` | WordPress server |
| Built React assets | `acm2-wordpress-plugin/plugin/assets/react-build` | WordPress server |

No file transfer between nodes. Build in place.

---

## 17) Fresh Windows Installation — Step by Step

**Tested January 28, 2026** - A complete guide to install ACM2 on a fresh Windows machine.

### Prerequisites
- Windows 10/11 with PowerShell
- Internet connection
- Administrator privileges

---

### Step 1: Install Git

**Option A: Manual Download**
1. Go to https://git-scm.com/download/win
2. Download the 64-bit installer
3. Run installer with default options
4. **Important**: Select "Git from the command line and also from 3rd-party software"

**Option B: PowerShell (if winget available)**
```powershell
winget install Git.Git --accept-package-agreements --accept-source-agreements
```

**Verify** (open NEW terminal after install):
```powershell
git --version
```

**Note**: If git is not recognized, you may need to refresh PATH:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

---

### Step 2: Install Python 3.11

```powershell
# Download Python installer
$pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$installer = "$env:TEMP\python-3.11.9-amd64.exe"
Invoke-WebRequest -Uri $pythonUrl -OutFile $installer

# Install silently with PATH (requires admin)
Start-Process -FilePath $installer -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1" -Wait

# CRITICAL: Refresh PATH in current session
$env:Path = "C:\Program Files\Python311;C:\Program Files\Python311\Scripts;" + $env:Path
```

**Verify**:
```powershell
python --version   # Expected: Python 3.11.9
pip --version      # Expected: pip 24.x
```

**Troubleshooting**: If python/pip not found, the PATH wasn't updated. Run the PATH refresh line above again.

---

### Step 3: Clone the Repository

```powershell
cd c:\devlop
git clone https://github.com/morganross/acm2
```

---

### Step 4: Install Python Dependencies

```powershell
cd c:\devlop\acm2\acm2
pip install -e .
```

This installs (~200+ packages):
- FastAPI + Uvicorn (API server)
- SQLAlchemy + aiosqlite + aiomysql (databases)
- gpt-researcher (research engine)
- OpenAI, Anthropic, Google SDKs
- bcrypt, jinja2, email-validator (auth & templating)
- All other dependencies from pyproject.toml

**Note**: This takes several minutes due to gpt-researcher's large dependency tree.

---

### Step 5: Generate Encryption Key

```powershell
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

**Copy the entire output line** (e.g., `ENCRYPTION_KEY=abc123...`) for the next step.

---

### Step 6: Create Environment File

Create file `c:\devlop\acm2\acm2\.env`:

```env
# Required - paste your generated key here
ENCRYPTION_KEY=your_generated_key_here
SEED_PRESET_ID=default
SEED_VERSION=1.0.0

# Optional - LLM provider API keys (can also be set per-user in UI)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...
# TAVILY_API_KEY=tvly-...
```

---

### Step 7: Create FilePromptForge Environment

Create file `c:\devlop\acm2\FilePromptForge\.env`:

```env
# At least one provider key required for FilePromptForge
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...
```

---

### Step 8: Start the Server

**For foreground mode** (blocks terminal, stops when terminal closes):
```powershell
cd c:\devlop\acm2\acm2
python cli.py serve
```

**For background mode** (survives terminal commands, recommended):
```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:Path = 'C:\Program Files\Python311;C:\Program Files\Python311\Scripts;' + `$env:Path; cd c:\devlop\acm2\acm2; python cli.py serve 2>&1 | Tee-Object -FilePath c:\devlop\server.log"
```

Server runs at: **http://127.0.0.1:8000**

---

### Step 9: Verify Installation

**Check server is running:**
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object LocalPort, State
```
Expected: `LocalPort: 8000, State: Listen`

**Open in browser:**
- http://127.0.0.1:8000/docs — API documentation (Swagger UI)
- http://127.0.0.1:8000/redoc — API documentation (ReDoc)

---

### Quick Reference — Single Script Install

```powershell
# Run these commands in order (after Git is installed)

# 1. Install Python
$pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
Invoke-WebRequest -Uri $pythonUrl -OutFile "$env:TEMP\python-installer.exe"
Start-Process -FilePath "$env:TEMP\python-installer.exe" -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1" -Wait
$env:Path = "C:\Program Files\Python311;C:\Program Files\Python311\Scripts;" + $env:Path

# 2. Clone and install
cd c:\devlop
git clone https://github.com/morganross/acm2
cd acm2\acm2
pip install -e .

# 3. Generate encryption key (save output!)
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# 4. Create .env files manually (see Steps 6 & 7)

# 5. Start server (background mode)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\devlop\acm2\acm2; python cli.py serve"
```

---

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `python` not recognized | Run PATH refresh: `$env:Path = "C:\Program Files\Python311;C:\Program Files\Python311\Scripts;" + $env:Path` |
| `git` not recognized | Open NEW terminal after Git install, or refresh PATH |
| Server exits immediately | Check `.env` file exists and has valid ENCRYPTION_KEY |
| Port 8000 already in use | Kill existing process: `Get-Process python \| Stop-Process -Force` |
| Missing module errors | Run `pip install -e .` again from acm2\acm2 folder |

---

### Server Management Commands

```powershell
# Check if server is running
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

# View server logs (if started with Tee-Object)
Get-Content c:\devlop\server.log -Tail 50

# Kill server
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Restart server (background)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\devlop\acm2\acm2; python cli.py serve"
```



---

## 14) Frontend Development Environment Setup

This section covers setting up a development environment on an EC2 Windows instance using VS Code Remote Tunnels.

### 14.1 SSH into EC2 via AWS Web Console

1. Go to **AWS Console** → **EC2** → **Instances**
2. Select your Windows instance
3. Click **Connect** → **RDP client** tab (or use **Session Manager** if configured)
4. For web-based access: Use **EC2 Instance Connect** or **Fleet Manager Remote Desktop**

### 14.2 Install VS Code CLI (Headless Remote Tunnel Host)

Run these commands in PowerShell on the EC2 instance:

```powershell
# 1. Download VS Code CLI
Invoke-WebRequest -Uri "https://code.visualstudio.com/sha/download?build=stable&os=cli-win32-x64" -OutFile "$env:TEMP\vscode-cli.zip"

# 2. Extract to a permanent location
Expand-Archive -Path "$env:TEMP\vscode-cli.zip" -DestinationPath "C:\vscode-cli" -Force

# 3. Add to PATH (current session)
$env:Path += ";C:\vscode-cli"

# 4. Add to PATH (permanent - requires admin)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\vscode-cli", [EnvironmentVariableTarget]::Machine)
```

### 14.3 Start the Remote Tunnel and Login via GitHub

```powershell
# Start the tunnel service (will prompt for GitHub login)
code tunnel

# First run will display:
# "To grant access to the server, please log into https://github.com/login/device
#  and use code: XXXX-XXXX"
```

**Steps:**
1. Copy the device code shown in the terminal
2. Open https://github.com/login/device in your browser
3. Paste the code and authorize "Visual Studio Code"
4. The tunnel will connect and show: `Connected to tunnel: <machine-name>`

### 14.4 Connect from Local VS Code

1. Open VS Code on your local machine
2. Install the **Remote - Tunnels** extension (if not already installed)
3. Press `F1` → **Remote-Tunnels: Connect to Tunnel...**
4. Sign in with the same GitHub account
5. Select your EC2 machine from the list
6. VS Code opens a remote session to the EC2 instance

### 14.5 Run Tunnel as Background Service (Optional)

To keep the tunnel running after you disconnect:

```powershell
# Install as a Windows service (run as Administrator)
code tunnel service install

# Start the service
code tunnel service start

# Check service status
Get-Service -Name "code-tunnel" -ErrorAction SilentlyContinue

# Uninstall service if needed
code tunnel service uninstall
```

### 14.6 Verification

Once connected via VS Code Remote Tunnel:
- Open terminal in VS Code: `Ctrl+` `
- Navigate to project: `cd c:\devlop\acm2`
- Verify server is running: `netstat -ano | findstr :80`

---

## 15) Frontend Development Setup (Linux/Bitnami Lightsail)

This is the recommended approach for setting up VS Code Remote Tunnel on a Linux Lightsail instance.

### 15.1 Overview

**Problem:** Copy-pasting multiple commands into a web SSH terminal is error-prone and tedious.

**Solution:** Use VS Code's Remote-SSH extension to connect first, then let Copilot Chat run the tunnel installation commands. After the tunnel is installed, switch to using the tunnel for future connections.

### 15.2 Prerequisites

On your **local machine**:
1. Install VS Code
2. Install the **Remote - SSH** extension
3. Install the **Remote - Tunnels** extension

On **Lightsail**:
1. Download your instance's SSH key from Lightsail console
2. Note your instance's public IP address

### 15.3 Connect via SSH (Bootstrap)

1. Open VS Code locally
2. Press `F1` → **Remote-SSH: Connect to Host...**
3. Enter: `bitnami@YOUR_INSTANCE_IP`
4. When prompted, select your downloaded `.pem` key file
5. VS Code opens a remote session via SSH

### 15.4 Install Tunnel via Copilot Chat

Once connected via SSH, open Copilot Chat and say:

> "Install VS Code tunnel on this Linux machine and start it"

Copilot will run these commands:

```bash
cd /tmp
curl -Lk "https://code.visualstudio.com/sha/download?build=stable&os=cli-linux-x64" -o code.tar.gz
tar -xzf code.tar.gz
sudo mv code /usr/local/bin/
code tunnel
```

### 15.5 Authenticate the Tunnel

When `code tunnel` runs, it will display:

```
To grant access to the server, please log into https://github.com/login/device
and use code: XXXX-XXXX
```

1. Open https://github.com/login/device in your browser
2. Enter the code shown in the terminal
3. Authorize "Visual Studio Code"
4. Terminal will show: `Connected to tunnel: <machine-name>`

### 15.6 Switch from SSH to Tunnel

1. Close the SSH connection (Close Remote Connection)
2. Press `F1` → **Remote-Tunnels: Connect to Tunnel...**
3. Sign in with the same GitHub account
4. Select your machine from the list
5. Done! You're now connected via tunnel

### 15.7 Keep Tunnel Running (Optional)

To run the tunnel as a background service so it persists after logout:

```bash
# Install as systemd service
code tunnel service install

# Start the service
sudo systemctl start code-tunnel

# Enable on boot
sudo systemctl enable code-tunnel
```

### 15.8 Why Tunnel over SSH?

| Feature | SSH | Tunnel |
|---------|-----|--------|
| Requires open port | Yes (22) | No |
| Requires SSH key | Yes | No |
| Works through firewalls | Sometimes | Always |
| GitHub authentication | No | Yes |
| Persistent connection | Manual | Automatic |

---

## 16) Clone Frontend Plugin Repo

the repo is cloned in place in the wordpress plugin folder.
the plugin folder has a sibling folder that is not a wordpressplugin.

---

## 18) VS Code Headless Tunnel — MVP Quick Install (Linux/Bitnami)

Minimal steps to get VS Code remote tunnel running on a fresh Bitnami Lightsail instance.

### Step 1: SSH into your instance via AWS web console

### Step 2: Run these commands one at a time

```bash
cd ~

curl -L "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64" -o vscode_cli.tar.gz

tar -xzf vscode_cli.tar.gz

sudo mv code /usr/local/bin/

rm vscode_cli.tar.gz

code tunnel user login --provider github
```

**WAIT** — it will show a code. Go to https://github.com/login/device and enter it. Wait for "Successfully logged in".

```bash
code tunnel rename YOUR-TUNNEL-NAME
```

### Step 3: Start the tunnel

```bash
code tunnel
```

Leave this running. Connect from VS Code: Remote Explorer → Tunnels → YOUR-TUNNEL-NAME

### Step 4: Ask Copilot to finish the install

Once connected via VS Code tunnel, open Copilot Chat and say:

> "Finish the VS Code tunnel install — set it up to run automatically as a service"

Copilot will run the systemd commands to make the tunnel start on boot and run 24/7.

### Step 4 (Manual Alternative): Run as background service

To run 24/7 without keeping SSH open:

```bash
sudo bash -c 'cat > /etc/systemd/system/code-tunnel.service << EOF
[Unit]
Description=VS Code Remote Tunnel
After=network.target

[Service]
Type=simple
User=bitnami
ExecStart=/usr/local/bin/code tunnel --accept-server-license-terms
Restart=always
RestartSec=10
Environment=HOME=/home/bitnami

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload

sudo systemctl enable code-tunnel

sudo systemctl start code-tunnel

sudo systemctl status code-tunnel
```

Should show "active (running)".

---

## 19) Connecting Backend to Frontend — Master Database Setup

The ACM2 backend (Windows) must connect to the MySQL master database on the frontend (Bitnami WordPress) for user authentication and API key management.

**IMPORTANT: Both instances are Lightsail — use PRIVATE IPs for MySQL connection!**
- Private IPs stay within AWS network (more secure, faster, free)
- No need to open port 3306 to public internet
- Find private IPs: Lightsail Console → Instance → Networking tab

**NOTE: Plugin auto-setup is NOT implemented yet.** The WordPress plugin does NOT automatically create the `acm2_master` database on activation. This is a future enhancement. For now, manual setup is required.

### 19.1 Architecture Overview

```
+-------------------------------------+     +-------------------------------------+
|  FRONTEND (Bitnami WordPress)       |     |  BACKEND (Windows Lightsail)        |
|  Public:  16.145.206.59             |     |  Public:  54.202.39.49              |
|  Private: 172.26.x.x                |     |  Private: 172.26.y.y                |
|                                     |     |                                     |
|  +-----------------------------+    |     |  +-----------------------------+    |
|  | WordPress + ACM2 Plugin     |    |     |  | ACM2 FastAPI Server         |    |
|  | - Serves React frontend     |<---+-----+--| - API endpoints             |    |
|  | - Proxies API requests      |    |     |  | - Run execution             |    |
|  +-----------------------------+    |     |  +--------------+--------------+    |
|                                     |     |                 |                   |
|  +-----------------------------+    |     |                 |                   |
|  | MySQL (Bitnami)             |<---+-----+-----------------+                   |
|  | - acm2_master database      |    |     |  Backend connects via PRIVATE IP   |
|  | - users table               |    |     |  (e.g., 172.26.x.x:3306)           |
|  | - api_keys table            |    |     |                                     |
|  +-----------------------------+    |     |  +-----------------------------+    |
|                                     |     |  | SQLite (per-user)            |    |
+-------------------------------------+     |  | - user_6.db, user_7.db, etc |    |
                                            |  | - presets, runs, documents  |    |
                                            |  +-----------------------------+    |
                                            +-------------------------------------+
```

### 19.2 Step 0: Get Private IPs

On each Lightsail instance, find the private IP:

```bash
# On any Lightsail instance
hostname -I
# or check Lightsail Console -> Instance -> Networking
```

Example:
- Frontend private IP: `172.26.10.50`
- Backend private IP: `172.26.10.100`

### 19.3 Step 1: Create ACM2 Master Database on Bitnami

SSH into the Bitnami frontend server:

```bash
# Get MySQL root password
cat /home/bitnami/bitnami_credentials

# Connect to MySQL
mysql -u root -p

# Create database and tables
CREATE DATABASE acm2_master CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE acm2_master;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    wordpress_user_id INT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    last_used_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_users_wordpress ON users(wordpress_user_id);
```

### 19.4 Step 2: Create MySQL User for Remote Access (Private IP)

Still in MySQL on the Bitnami server:

```sql
-- Create user that can connect from the backend's PRIVATE IP
-- Replace 172.26.10.100 with your backend's actual private IP
CREATE USER 'acm2_backend'@'172.26.10.100' IDENTIFIED BY 'YOUR_STRONG_PASSWORD_HERE';

-- Grant permissions on the acm2_master database
GRANT SELECT, INSERT, UPDATE, DELETE ON acm2_master.* TO 'acm2_backend'@'172.26.10.100';

FLUSH PRIVILEGES;

-- Verify the user was created
SELECT User, Host FROM mysql.user WHERE User = 'acm2_backend';

EXIT;
```

### 19.5 Step 3: Configure MySQL to Listen on Private IP

```bash
# Check current MySQL bind address
sudo netstat -tlnp | grep 3306

# Edit MySQL config
sudo nano /opt/bitnami/mysql/conf/my.cnf

# Find bind-address and change to the frontend's PRIVATE IP:
# bind-address = 172.26.10.50
#
# Or to listen on all interfaces:
# bind-address = 0.0.0.0

# Restart MySQL
sudo /opt/bitnami/ctlscript.sh restart mysql

# Verify MySQL is now listening on the private IP
sudo netstat -tlnp | grep 3306
```

### 19.6 Step 4: Lightsail Firewall (Private Network)

**Good news:** Lightsail instances in the same region can communicate on private IPs without firewall changes. The default Lightsail firewall only affects PUBLIC traffic.

**No firewall changes needed** if using private IPs.

(If you must use public IPs, add port 3306 in Lightsail Networking, restricted to backend public IP only.)

### 19.7 Step 5: Configure Backend Environment Variables

On the Windows backend, add to `c:\devlop\acm2\acm2\.env`:

```env
# Master Database (MySQL on Bitnami frontend via PRIVATE IP)
MASTER_DB_HOST=172.26.10.50
MASTER_DB_USER=acm2_backend
MASTER_DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
MASTER_DB_NAME=acm2_master
```

**Replace `172.26.10.50` with your frontend's actual private IP.**

### 19.7 Step 6: Update Backend Code to Read Env Vars

The `master.py` file needs to read credentials from environment variables instead of using hardcoded defaults. This is a code change in `acm2/app/db/master.py`.

### 19.8 Step 7: Test the Connection

From the Windows backend, create a test script or run:

```powershell
python -c "import asyncio; import aiomysql; import os; asyncio.run((lambda: print('Test requires manual verification'))())"
```

### 19.9 Verification Checklist

- [ ] `acm2_master` database exists on Bitnami MySQL
- [ ] `users` and `api_keys` tables created
- [ ] MySQL user created with remote access from backend IP
- [ ] MySQL listening on 0.0.0.0:3306 (not just localhost)
- [ ] Bitnami firewall allows port 3306 from backend IP
- [ ] AWS Security Group allows port 3306 from backend IP
- [ ] Backend `.env` has correct `MASTER_DB_*` variables
- [ ] Backend code reads env vars for MySQL connection
- [ ] Test connection succeeds from backend
- [ ] WordPress user creation triggers ACM2 user creation

### 19.10 Troubleshooting

**"Can't connect to MySQL server"**
- Check MySQL is running: `sudo /opt/bitnami/ctlscript.sh status mysql`
- Check MySQL is listening on 0.0.0.0: `sudo netstat -tlnp | grep 3306`
- Check firewall rules on both Bitnami and AWS

**"Access denied for user"**
- Verify username and password
- Check the user host matches backend IP exactly
- Run `SELECT User, Host FROM mysql.user;` to verify

**"Unknown database 'acm2_master'"**
- Database wasn't created; run the CREATE DATABASE command

**Connection times out**
- AWS Security Group not open for port 3306
- Backend IP changed (check with `curl ifconfig.me` on backend)
