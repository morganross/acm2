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
