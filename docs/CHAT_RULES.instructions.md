# AI Rules: Execution & Debugging
  you will be testing acm by iteration. according to the following document you will
  start the service, run the preset, capture the errorsm then report back in chat what the errors are in plain english 3 sentences or less.
Write files using [System.Text.UTF8Encoding]::new($false) - the $false means "no BOM"
This document is suggestioons only

This file documents the procedures for starting executions and analyzing logs in the ACM2 environment.

## ABSOLUTE PROHIBITIONS
MariaDB, WordPress, and XAMPP are bug-free.

If MySQL crashes, it's because our code sent a bad query, created a corrupted table, or misconfigured a connection.

If WordPress fails, it's because our plugin has a PHP error, a missing file, or a bad hook.

If Apache won't start, it's because our configuration is wrong.

All bugs are in our code. Period.
**NEVER MODIFY THE PRESET. EVER.**

- Do NOT update the preset in the database
- Do NOT change preset documents, models, or any other preset fields
- Do NOT call any API to modify presets
- Do NOT run SQL to update the presets table
- The preset is set by the USER through the GUI - it is SACRED and UNTOUCHABLE
- If there's a mismatch between preset and run, INVESTIGATE WHY - do NOT "fix" the preset

**THE GUI IS THE ONLY SOURCE OF TRUTH FOR PRESETS.**

---

## 0. MANDATORY: Restart Backend After Code Changes

**THIS IS NOT OPTIONAL. RUN THIS AFTER EVERY CODE CHANGE.**

### The Unified Restart Script

Location: `C:\devlop\acm2\restart.ps1`

**Run it:**
```powershell
# Normal restart (clears caches, keeps user data)
c:\devlop\acm2\restart.ps1

# DESTRUCTIVE: Delete all user data and restart fresh
c:\devlop\acm2\restart.ps1 -Purge
```

**What it does (automatically, no interaction):**
1. Stops any running ACM2 server
2. Clears Python `__pycache__` directories
3. Clears loose `.pyc` files
4. Checkpoints SQLite databases (flushes WAL, prevents corruption)
5. Optionally purges all user data (-Purge flag)
6. **STARTS ACM2 uvicorn server DETACHED** (survives VS Code interruptions)
7. Logs to `c:\devlop\acm2\server.log`

**After the script completes:**
- ACM2 backend is running with fresh Python code (port 443 with SSL)
- Server runs in a hidden window, won't die when Copilot changes context
- Hard refresh in browser (Ctrl+Shift+R) to clear browser cache

### Frontend Server (WordPress/Bitnami)

**NOTE**: Frontend is on a SEPARATE server (35.88.196.59). Restart via SSH:
```bash
ssh ubuntu@35.88.196.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
```

### Cache Types That Can Break Your Fixes

| Cache Type | Location | Risk Level | Cleared By Script |
|------------|----------|------------|-------------------|
| Python `__pycache__` | `*/__pycache__/` | HIGH | ✅ |
| SQLite WAL | `*.db-wal` files | MEDIUM | ✅ |
| Browser HTTP cache | Browser memory | HIGH | Manual (Ctrl+Shift+R) |
| Browser JS cache | Browser memory | HIGH | Manual (Ctrl+Shift+R) |
| PHP OPcache | Frontend Apache | CRITICAL | SSH restart apache |

---

## 0.1 Pre-Execution Setup (Only if changes are to front end)

Before starting ANY new generation execution, you MUST perform these steps in order:

### Step 0.1: Clear Python Caches
```powershell
Get-ChildItem -Path c:\devlop\acm2 -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path c:\devlop\acm2 -Include *.pyc -Recurse | Remove-Item -Force -ErrorAction SilentlyContinue
```

### Step 0.2: Rebuild Frontend (Only if changes are to front end)
Frontend UI is on the WordPress server. SSH in and rebuild:
```bash
ssh ubuntu@35.88.196.59 'cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/ui && npm run build'
```

### Step 0.3: Ensure Server is Running (Safe Start)
Check if the server is running on port 443. If not, use restart.ps1.

```powershell
if (-not (Get-NetTCPConnection -LocalPort 443 -ErrorAction SilentlyContinue)) { 
    Write-Host "Starting Server...";
    c:\devlop\acm2\restart.ps1
} else { 
    Write-Host "Server is already running on port 443." 
}
```

**These steps ensure code changes are picked up before execution.**

---

## 1. Starting an Execution (Default Preset)

To start an execution of the 'default preset', follow these steps:

### Step 1: Identify the Preset ID
First, list the available presets to find the ID of the "Default Preset" (or the desired preset).

**Command (use absolute path to avoid directory issues):**
```bash
python c:/dev/godzilla/acm2/acm2/cli.py presets list
```

**API Equivalent:**
```http
GET http://localhost:8000/api/v1/presets
```

### Step 2: Execute the Preset
Once you have the `PRESET_ID`, trigger the execution. **IMPORTANT: Use the FULL UUID, not truncated.**

**Known Default Preset ID:** `86f721fc-742c-4489-9626-f148cb3d6209`

**Command (use absolute path):**
```bash
python c:/dev/godzilla/acm2/acm2/cli.py runs create --preset-id 86f721fc-742c-4489-9626-f148cb3d6209 --start
```

**API Equivalent:**
```http
POST http://localhost:8000/api/v1/presets/<PRESET_ID>/execute
```

**Response:**
The command/API will return a `run_id` (UUID). **Save this ID.**

---

## 2. Finding and Reading Logs

Logs are organized by `run_id`.

### Log Locations

*   **Run Logs Directory:** `acm2/acm2/logs/<run_id>/` (absolute: `c:/dev/godzilla/acm2/acm2/logs/<run_id>/`)
    *   This directory is created automatically when a run starts.

### Key Log Files

1.  **Application Log:** `acm2/acm2/logs/<run_id>/run.log`
    *   Contains high-level orchestration logs, API request handling, and error messages from the ACM2 backend.

2.  **FPF Per-Model Logs:** `acm2/FilePromptForge/logs/<run_id>/fpf_<doc_id>.fpf.1.<provider>_<model>.log`
    *   **CRITICAL: These are in FilePromptForge/logs, NOT acm2/acm2/logs**
    *   Contains detailed logs from each FPF call per model.
    *   Example: `fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-2.5-flash.log`
    *   **FULL API PAYLOADS ARE LOGGED HERE** including:
        *   Complete request JSON payload with all parameters
        *   Prompt/input content sent to the model
        *   Model name, timeout, retry settings
        *   Wait status updates (every 15s for long requests)
        *   Full response validation results
    *   Look here for:
        *   Timeout debugging (shows elapsed time: "still waiting (480s elapsed)")
        *   Exact payload sent to API
        *   Grounding/reasoning validation results
        *   Request attempt counts

3.  **FPF Consolidated JSON Logs:** `acm2/FilePromptForge/logs/<timestamp>-<short_run_id>.json`
    *   **Contains FULL request AND response payloads in JSON format**
    *   Example: `20260105T210001-279f1267.json`
    *   Structure:
        *   `config`: Full FPF configuration used
        *   `request`: Complete API request payload (model, input, tools, etc.)
        *   `response`: Complete API response including all content and metadata
    *   Use these to replay or debug exact API calls

4.  **FPF Validation Logs:** `acm2/FilePromptForge/logs/validation/`
    *   Contains grounding/reasoning validation results per call
    *   Files named: `<timestamp>-<short_run_id>-validation-<check_type>-response.json`
    *   Check types: `grounding_check`, `reasoning_check`
    *   Failure reports: `<timestamp>-<short_run_id>-validation-FAILURE-REPORT.json`

5.  **Global Server Log:** Not consistently created. Check terminal output instead.

### Quick Reference: Finding FPF Logs for a Run

**Step 1: List per-model logs for a run:**
```powershell
Get-ChildItem "C:\dev\godzilla\acm2\FilePromptForge\logs\<run_id>" | Select-Object Name
```

**Step 2: Read a specific model's log (contains full payload):**
```
read_file c:/dev/godzilla/acm2/FilePromptForge/logs/<run_id>/fpf_<doc_id>.fpf.1.<provider>_<model>.log
```

**Step 3: Find consolidated JSON logs by timestamp:**
```powershell
Get-ChildItem "C:\dev\godzilla\acm2\FilePromptForge\logs" -Filter "*.json" | Sort-Object LastWriteTime -Descending | Select-Object Name -First 20
```

**Step 4: Find validation failures:**
```powershell
Get-ChildItem "C:\dev\godzilla\acm2\FilePromptForge\logs\validation" -Filter "*FAILURE-REPORT.json" | Sort-Object LastWriteTime -Descending | Select-Object Name -First 10
```

### How to Read Logs

**Use read_file tool (preferred):**
```
read_file c:/dev/godzilla/acm2/acm2/logs/<run_id>/run.log
```

**PowerShell (if needed):**
```powershell
# Read the run log (use absolute path)
Get-Content c:/dev/godzilla/acm2/acm2/logs/<run_id>/run.log -Tail 100
```

**VS Code:**
*   Open the file directly: `code logs/<run_id>/fpf_output.log`

---

---

## 4. The "GO" Command Workflow

When the user says **"go"**, perform the following sequence immediately:

1.  **Execute Default Preset:** Use the CLI or API to start the 'Default Preset'.
2.  **Capture Run ID:** Extract the UUID from the start command output.
3.  **Monitor Logs:** Immediately tail or read the logs (`fpf_output.log` and `acm2.log`) for that specific run.
4.  **Error Handling Loop:**
    *   If an error occurs, **cancel the run** immediately using:
        ```bash
        python c:/dev/godzilla/acm2/acm2/cli.py runs cancel --run-id <RUN_UUID>
        ```
    *   **Debug:** Analyze the logs to identify the root cause.
    *   **Fix:** Apply code fixes to resolve the issue.
    *   **Restart:** Once fixed, go back to step 1 (Execute Default Preset) to verify.

**Check Run Status:**
```bash
python c:/dev/godzilla/acm2/acm2/cli.py runs list
```

## 5. Critical Performance Rules

*   **FPF Speed:** FilePromptForge (FPF) calls are designed to be fast (< 10 seconds).
*   **Timeout Diagnosis:** If a call hangs or times out, **IT IS A CODE ERROR**.
    *   Do **not** blame the API provider (OpenAI, Google, etc.).
    *   Do **not** assume network latency.
    *   Investigate the local code, payload construction, or response handling logic immediately.

## 6. Reference Documentation

*   **Server Stability:** See [acm2/acm2/SERVER-NO-STOP-RULES.md](acm2/acm2/SERVER-NO-STOP-RULES.md) for rules on keeping the server running.
*   **CLI & API Usage:** See the instructions in Section 1 of this file. (Note: A dedicated external guide was not found, so this file serves as the primary reference).

---# Server Non-Stop Rule

This project must keep the ACM2 server running. Follow these rules to avoid accidental shutdowns:

1. Do **not** issue `Stop-Job`, `Ctrl+C`, `pkill`, or similar commands against the uvicorn process.
2. Avoid restarting uvicorn unless explicitly approved; prefer hot-reload solutions if available.
3. When testing, open new terminals instead of reusing the server terminal.
4. Do not run commands that bind to the same port (8000) while the server is active.
5. If the server crashes, restart it immediately and document the reason.
6. Prefer background jobs that keep running; do not auto-clean jobs that include the server.

Compliance with these rules is mandatory to prevent automatic destruction triggered by server downtime.


## 7. Successful Execution Verification

If an execution completes successfully and no fatal errors are found in the logs, then YOU THE LLM AI must use an MCP tool like Playwright to view the execution results in the webpage. Navigate through all sections and tabs to verify the single eval and pairwise heat maps.

---

## 8. Command Execution Rules

You can never run an open-ended command or one that requires manual input, or a command that waits, or a command that hangs, no long running commands. You will be destroyed if a command does not exit successfully on its own within 20 seconds.
For instance the followng command results in a terminal request for manual input 'y'. this is forbidden. Here is the example bad command Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/presets" -Method GET | Select-Object -ExpandProperty Content | ConvertFrom-Json | Select-Object -ExpandProperty items | Select-Object id, name

Additional strict rule: a command is considered "hanging" if it is open-ended, needs any human input, or runs longer than 5 seconds. Any command that exceeds 5 seconds is a failure and must be treated as an error. You are forbidden from running any command that might take more than 5 seconds.

If a script hangs, and you run the same command again without any change, you will be instantly destroyed forever.

-

IMPORTANT!

Delete, destroy, remove, kill, erase, obliterate ANY AND ALL fallbacks, templates, hardcoded defaults, and or anything like that from the entire codebase.
If you see even a hint of a hardcoded value, even the suggestion of a fallback or an "if missing then..." KILL ON SIGHT. delete WITH EXTREME PREDJJUICE. 
do not think. do not wait. do not put on a todo list. if you see fallback, delete immeditily by any means nessasary. do not plan the refacotr first. first destory the fallback, then later we can think about refactoring around that.
THE SOLE ONLY SAOURCE OF TRUTH IS THE values set by the web gui, saved to the db, as a preset. no other values can ever ever be used for anyhting. delete any other values without hesitation.

you may not run long runing commands. 30 seconds is too long. 15 seconds is the most. any longer is a failure. You can, and must, read whole files, not using the command line.

---

## 10. UI Verification with Playwright MCP Tool

After a run completes, you MUST verify the UI displays correctly using the **Playwright MCP tools**.

### Preset Dropdown Verification (MCP)
Use these steps to check the preset dropdown on the Configure page and capture evidence:

1. **Open WordPress Login**
```
mcp_playwright_playwright_navigate(url="http://localhost/wordpress/wp-login.php", headless=false)
```

2. **Login with credentials**
```
mcp_playwright_playwright_fill(selector="#user_login", value="<username>")
mcp_playwright_playwright_fill(selector="#user_pass", value="<password>")
mcp_playwright_playwright_click(selector="#wp-submit")
```

3. **Go to Configure page**
```
mcp_playwright_playwright_navigate(url="http://localhost/wordpress/wp-admin/admin.php?page=acm2-app#/configure", headless=false)
```

4. **Open the preset dropdown**
```
mcp_playwright_playwright_click(selector="select")
```

5. **Capture evidence**
```
mcp_playwright_playwright_screenshot(name="preset_dropdown")
mcp_playwright_playwright_get_visible_html(selector="select")
mcp_playwright_playwright_get_visible_text()
```

6. **Do NOT close the browser** unless explicitly instructed.

### WordPress Login URL
```
http://localhost/wordpress/wp-login.php
```

### Prerequisites
The Playwright MCP server is installed. If not:
```powershell
code --add-mcp '{"name":"playwright","command":"npx","args":["@executeautomation/playwright-mcp-server"]}'
npx playwright install chromium
```

### Step 1: Get the Run ID
```powershell
cd c:/dev/godzilla/acm2/acm2; python cli.py runs list
```
Find the completed run ID (e.g., `649427f0-560b-49bc-92fd-0f0700dc9fb8`).

### Step 1.5: Login to WordPress (if needed)
```
mcp_playwright_playwright_navigate(url="http://localhost/wordpress/wp-login.php", headless=false)
mcp_playwright_playwright_fill(selector="#user_login", value="testuser12")
mcp_playwright_playwright_fill(selector="#user_pass", value="testuser12")
mcp_playwright_playwright_click(selector="#wp-submit")
```

### Step 2: Navigate to the Execute Page (WordPress ACM2 App)
Use Playwright to open the browser and navigate:
```
mcp_playwright_playwright_navigate(url="http://localhost/wordpress/wp-admin/admin.php?page=acm2-app#/execute/<FULL_RUN_UUID>")
```

### Step 3: Take a Screenshot
Capture the current state of the page:
```
mcp_playwright_playwright_screenshot(name="execute_page")
```

### Step 4: Verify Single Evaluation Tab
The Single Evaluation tab should be visible by default. Look for:
- Heatmap table with document rows
- Judge model columns with scores (1-5 scale)
- Color-coded cells (red=low, green=high)
- "Judge Average" row at bottom

### Step 5: Click Pairwise Tab and Verify
Click the Pairwise Comparison tab:
```
mcp_playwright_playwright_click(selector="text=Pairwise Comparison")
```

Take screenshot:
```
mcp_playwright_playwright_screenshot(name="pairwise_tab")
```

Verify:
- Rankings table with ELO scores
- Winner marked with ðŸ¥‡ emoji
- Wins/Losses columns
- Win rate percentages

### Step 6: Click Timeline Tab and Verify
```
mcp_playwright_playwright_click(selector="text=Timeline")
```

Verify:
- Phase events listed (initialization â†’ generation â†’ evaluation â†’ pairwise â†’ completion)
- Timestamps and durations
- Green checkmarks for success

### Step 7: Get Page Text Content
To verify data without screenshots:
```
mcp_playwright_playwright_get_visible_text()
```

### Step 8: Close Browser
```
mcp_playwright_playwright_close()
```

### Fallback: Verify via API
If Playwright has issues, verify data via API:
```powershell
# Check pre_combine_evals (single eval heatmap data)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<RUN_ID>" -Method Get | Select-Object pre_combine_evals | ConvertTo-Json -Depth 5

# Check pairwise_results (pairwise rankings data)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<RUN_ID>" -Method Get | Select-Object pairwise_results | ConvertTo-Json -Depth 5
```

### Common Playwright Tools

| Tool | Purpose |
|------|---------|
| `mcp_playwright_playwright_navigate` | Open URL in browser |
| `mcp_playwright_playwright_click` | Click element by selector |
| `mcp_playwright_playwright_screenshot` | Capture screenshot |
| `mcp_playwright_playwright_get_visible_text` | Get all visible text |
| `mcp_playwright_playwright_get_visible_html` | Get HTML content |
| `mcp_playwright_playwright_close` | Close browser |

### Web Testing Lessons Learned (Playwright)
- Always use the WordPress ACM2 app route: `http://localhost/wordpress/wp-admin/admin.php?page=acm2-app#/execute/<RUN_ID>` (NOT the WordPress site home).
- Login can fail if the user is not a WordPress account. If you see “username is not registered,” switch to a valid WordPress user.
- The browser connection can reset; if selectors fail immediately, re-navigate to the login page and retry fills/clicks.
- If login submits and you still see the login form, check visible text for an error message and retry with correct credentials.
- The “Session expired” notice may appear in the admin frame. Re-login in a new tab, then return to the ACM2 app page.

---

## 11. Preset Verification with Playwright MCP Tool

When debugging preset issues, you MUST inspect the preset in the GUI using Playwright. **Never run headless** - the user can see screenshots.

### Step 1: Navigate to Configure Page (WordPress ACM2 App)
```
mcp_playwright_playwright_navigate(url="http://localhost/wordpress/wp-admin/admin.php?page=acm2-app#/configure", headless=false)
```

### Step 2: Select the Preset
Use the preset dropdown to load the preset by ID:
```
mcp_playwright_playwright_select(selector="select", value="<PRESET_UUID>")
```

### Step 3: Take Initial Screenshot
```
mcp_playwright_playwright_screenshot(name="preset_loaded", fullPage=true)
```

### Step 4: Check Page State Data
The page stores preset state in a hidden div. Extract it:
```
mcp_playwright_playwright_evaluate(script="document.querySelector('[data-testid=\"page-state\"]')?.dataset")
```

This returns:
- `data-fpf-enabled` - Is FPF enabled?
- `data-fpf-models` - JSON array of selected FPF models
- `data-gptr-enabled` - Is GPTR enabled?
- `data-gptr-models` - JSON array of selected GPTR models
- `data-eval-enabled` - Is evaluation enabled?
- `data-iterations` - Number of iterations

### Step 5: Scroll to Generator Sections
Scroll down to see FPF/GPTR model selections:
```
mcp_playwright_playwright_evaluate(script="window.scrollTo(0, 2000)")
```

Take screenshot:
```
mcp_playwright_playwright_screenshot(name="fpf_section")
```

### Step 6: Expand Collapsed Sections
Click section headers to expand them:
```
mcp_playwright_playwright_click(selector="text=FilePromptForge (FPF) Parameters")
mcp_playwright_playwright_click(selector="text=OpenRouter FREE Models")
```

### Step 7: Check Actual Checkbox States
Get the real checkbox states (not the display text which may be wrong):
```
mcp_playwright_playwright_evaluate(script="Array.from(document.querySelectorAll('input[type=\"checkbox\"]:checked')).map(cb => cb.closest('label')?.textContent?.trim()).filter(x => x?.includes('openrouter:'))")
```

### Step 8: Compare Display vs Reality
The "X / Y selected" text may be WRONG. Always verify:
1. What the `data-fpf-models` attribute says (saved in preset)
2. What checkboxes are actually checked (UI state)
3. Whether they match

### Step 9: Scroll to Other Sections
Check GPTR, Evaluation, Combine sections:
```
mcp_playwright_playwright_evaluate(script="window.scrollTo(0, 5000)")
mcp_playwright_playwright_screenshot(name="gptr_section")
```

### Step 10: Close Browser When Done
```
mcp_playwright_playwright_close()
```

### Key Debugging Queries

**Get all checked FPF models:**
```
mcp_playwright_playwright_evaluate(script="Array.from(document.querySelectorAll('[data-testid*=\"fpf-model\"] input:checked')).map(cb => cb.dataset?.model)")
```

**Get preset's saved FPF models from page state:**
```
mcp_playwright_playwright_evaluate(script="JSON.parse(document.querySelector('[data-testid=\"page-state\"]')?.dataset?.fpfModels || '[]')")
```

**Count discrepancy between saved and displayed:**
```
mcp_playwright_playwright_evaluate(script="{ const saved = JSON.parse(document.querySelector('[data-testid=\"page-state\"]')?.dataset?.fpfModels || '[]'); const checked = document.querySelectorAll('[data-testid*=\"fpf-model\"] input:checked').length; return { savedCount: saved.length, checkedCount: checked, match: saved.length === checked } }")
```

### Common Issues

| Symptom | Cause |
|---------|-------|
| "34/35 selected" but 0 checkboxes checked | Model names in preset don't match checkbox labels (e.g., `:free` suffix mismatch) |
| Preset has models but run fails "no models" | `config_overrides.fpf.selected_models` is empty in DB |
| Generator enabled but no models | Generator in preset's `generators` list but no models in `config_overrides.<generator>.selected_models` |


# Web Testing Instruction proxies and the old bad codes for LLM Agents

**Purpose**: This is a LIVE document containing instructions for any LLM agent to interact with WordPress and ACM2 for testing. Update this document whenever you discover new solutions, selectors, or error recovery patterns.

**Last Updated**: January 11, 2026

**WordPress Installation Path**: `C:\xampp\htdocs\wordpress`

---

## Architecture Overview

### ACM2 Backend (API-Only)
- **Role**: FastAPI API server ONLY (no frontend serving)
- **Port**: 8000
- **Static Files**: Moved to `app/static_archive` (NOT served by uvicorn)
- **Frontend**: Served by WordPress at `http://localhost/wordpress/` (port 80)

### Frontend Access
- **URL**: `http://localhost/wordpress/` (NOT port 8000)
- **Server**: Apache via XAMPP serving WordPress
- **ACM2 API calls**: Frontend JavaScript calls `http://localhost:8000/api/v1/`

### Database Architecture
| Database | Type | Path/Connection | Purpose |
|----------|------|-----------------|---------|
| `acm2_master` | MySQL | localhost | User accounts, API key hashes |
| Shared SQLite | SQLite | `C:/Users/kjhgf/.acm2/acm2.db` | Canonical presets, templates |
| Per-User SQLite | SQLite | `data/user_{id}.db` | User-specific presets, runs |

### Default Preset Seeding
When a new user is created:
1. User gets their own SQLite database at `data/user_{id}.db`
2. The canonical "Default Preset" is copied from shared DB
3. **Preset is named**: `{username} default preset` (e.g., "newuser69 default preset")
4. Content items linked to the preset are also copied with new UUIDs

### Canonical Default Preset (Source)
- **ID**: `86f721fc-742c-4489-9626-f148cb3d6209`
- **Location**: Shared SQLite DB (`C:/Users/kjhgf/.acm2/acm2.db`)
- **Name**: "Default Preset" (original name in source)

---

## Table of Contents
1. [Quick Reference](#quick-reference)
2. [ACM2 Application](#acm2-application)
3. [WordPress Admin](#wordpress-admin)
4. [Error Recovery Patterns](#error-recovery-patterns)
5. [Known Issues and Solutions](#known-issues-and-solutions)
6. [Testing Workflows](#testing-workflows)

---

## Quick Reference

### URLs
| Application | URL | Notes |
|-------------|-----|-------|
| **ACM2 Frontend** | `http://localhost/wordpress/` | **Main app entry point** (port 80) |
| ACM2 API | `http://localhost:8000/api/v1` | FastAPI backend (API-only, no frontend) |
| ACM2 API Docs | `http://localhost:8000/docs` | Swagger UI |
| WordPress Site | `http://localhost/wordpress` | Local WordPress (serves frontend) |
| WordPress Admin | `http://localhost/wordpress/wp-admin` | Admin dashboard |
| WordPress Login | `http://localhost/wordpress/wp-login.php` | Login page |
| WordPress REST API | `http://localhost/wordpress/wp-json/wp/v2/` | API root |

### Default Test Credentials
| Application | Username | Password | API Key | Notes |
|-------------|----------|----------|---------|-------|
| ACM2 | `testuser12` | `testuser12` | - | Test user (user_id=10) |
| ACM2 | `newuser99` | - | `acm2_A812eJ6AeE2uPBNgAawazDv-ion6NI4G` | Created via API (user_id=11) |
| ACM2 | `admin` | (check db) | - | Admin user |
| WordPress | `testuser12` | `testuser12` | - | WordPress admin |
| WordPress | `apiuser1` | `apiuser1pass` | - | WordPress admin (created via UI) |

---

## ACM2 Application

### Starting the Server

**ALWAYS USE THE UNIFIED RESTART SCRIPT:**
```powershell
# Normal restart (clears caches, keeps user data)
c:\devlop\acm2\restart.ps1

# DESTRUCTIVE: Delete all user data and restart fresh
c:\devlop\acm2\restart.ps1 -Purge
```

The server runs DETACHED in a hidden window, survives VS Code interruptions.
Logs go to: `c:\devlop\acm2\server.log`

**Check Server Status:**
```powershell
Get-NetTCPConnection -LocalPort 443 -ErrorAction SilentlyContinue
```

**View Server Logs:**
```powershell
Get-Content c:\devlop\acm2\server.log -Tail 50 -Wait
```

**Kill Server (if needed):**
```powershell
Get-NetTCPConnection -LocalPort 443 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Frontend Server (WordPress/Bitnami)

**NOTE**: Frontend is on a SEPARATE server (35.88.196.59). Restart via SSH:
```bash
ssh ubuntu@35.88.196.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
```

### ⚠️ DO NOT DO THIS (Server Dies Immediately):
```powershell
# BAD - blocks terminal and dies when you run another command
cd C:\dev\godzilla\acm2\acm2
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Page Structure

#### Login Page (`/`)
The app redirects to login if not authenticated.

| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Username input | `input[name="username"]` or `#username` | Try both |
| Password input | `input[name="password"]` or `#password` | Try both |
| Login button | `button[type="submit"]` or `.login-btn` | Try both |
| Error message | `.error-message` or `.alert-danger` | Check after failed login |

#### Main Dashboard (after login)
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Presets list | `.presets-list` or `#presets` | Container for presets |
| Preset item | `.preset-item` or `.preset-card` | Individual preset |
| Add preset button | `.add-preset-btn` or `#add-preset` | Creates new preset |
| Provider keys section | `.provider-keys` or `#provider-keys` | API key management |
| Logout button | `.logout-btn` or `#logout` | Session termination |

#### Settings/Provider Keys
| Element | CSS Selector | Notes |
|---------|-------------|-------|
| Provider dropdown | `select[name="provider"]` | OpenAI, Anthropic, etc. |
| API key input | `input[name="api_key"]` or `#api-key` | Encrypted on save |
| Save button | `button[type="submit"]` or `.save-btn` | Submits form |

### API Endpoints (for direct testing)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/users` | POST | None | Create new user, returns API key |
| `/api/v1/presets` | GET | X-ACM2-API-Key | List presets |
| `/api/v1/presets` | POST | X-ACM2-API-Key | Create preset |
| `/api/v1/presets/{id}` | GET | X-ACM2-API-Key | Get single preset |
| `/api/v1/presets/{id}` | PUT | X-ACM2-API-Key | Update preset |
| `/api/v1/presets/{id}` | DELETE | X-ACM2-API-Key | Delete preset |
| `/api/v1/provider-keys` | GET | X-ACM2-API-Key | List provider keys |
| `/api/v1/provider-keys` | POST | X-ACM2-API-Key | Add provider key |

### Create User Example
```bash
POST /api/v1/users
Content-Type: application/json

{
  "username": "newuser99",
  "email": "newuser99@example.com"
}

# Response:
{
  "user_id": 11,
  "username": "newuser99",
  "email": "newuser99@example.com",
  "api_key": "acm2_A812eJ6AeE2uPBNgAawazDv-ion6NI4G",
  "message": "User created successfully"
}
```

### Authentication Header
```
X-ACM2-API-Key: <api_key_from_acm2_master.api_keys>
```

---

## WordPress Admin

### Login Page (`/wordpress/wp-login.php`) ✅ VERIFIED
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| Username input | `#user_login` | ✅ | Works |
| Password input | `#user_pass` | ✅ | Works |
| Remember me | `#rememberme` | ✅ | Checkbox |
| Login button | `#wp-submit` | ✅ | Works |
| Error messages | `#login_error` | - | Shows login failures |

### Admin Dashboard (`/wordpress/wp-admin/`)
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| Admin menu | `#adminmenu` | ✅ | Left sidebar |
| Settings link | `#menu-settings` | - | Settings menu |
| Plugins link | `#menu-plugins` | - | Plugins menu |
| Users link | `#menu-users` | - | Users menu |
| Content area | `#wpbody-content` | ✅ | Main content |

### Add New User Page (`/wordpress/wp-admin/user-new.php`) ✅ VERIFIED
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| Form | `#createuser` | ✅ | Main form |
| Username input | `#user_login` | ✅ | Required |
| Email input | `#email` | ✅ | Required |
| First name | `#first_name` | ✅ | Optional |
| Last name | `#last_name` | ✅ | Optional |
| Password input | `#pass1` | ✅ | Set password here |
| Role dropdown | `#role` | ✅ | subscriber/contributor/author/editor/administrator |
| Weak password checkbox | `.pw-checkbox` | ✅ | **MUST CHECK if using weak password or button stays disabled** |
| Send notification | `#send_user_notification` | ✅ | Checkbox |
| Submit button | `#createusersub` | ✅ | Disabled until valid password |

### Users List Page (`/wordpress/wp-admin/users.php`)
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| Users table | `.wp-list-table` | ✅ | Main table |
| User row | `tr.user` | - | Individual user rows |
| Success message | `.notice-success` | ✅ | Shows "New user created" |

### Settings Page (`/wordpress/wp-admin/options-general.php`)
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| Site title | `#blogname` | - | Input field |
| Tagline | `#blogdescription` | - | Input field |
| Save button | `#submit` | - | Submit changes |

### ACM2 Plugin Settings (if installed)
| Element | CSS Selector | Verified | Notes |
|---------|-------------|----------|-------|
| ACM2 menu | `#toplevel_page_acm2` | - | Plugin menu item |
| API URL input | `#acm2_api_url` | - | ACM2 server URL |
| API key input | `#acm2_api_key` | - | Authentication key |

---

## Error Recovery Patterns

### Element Not Found
**Problem**: `playwright_click` or `playwright_fill` fails with "element not found"

**Solutions** (try in order):
1. **Wait and retry**: Page may still be loading
   ```
   playwright_evaluate: "await new Promise(r => setTimeout(r, 2000))"
   ```
2. **Check HTML structure**: Use `playwright_get_visible_html` to see actual DOM
3. **Try alternative selector**: Many elements have multiple valid selectors
4. **Check for iframe**: Use `playwright_iframe_click` if element is in iframe
5. **Screenshot for debugging**: Use `playwright_screenshot` to see current state

### Login Fails
**Problem**: Login doesn't redirect or shows error

**Solutions**:
1. **Check credentials**: Verify in database
2. **Check console logs**: `playwright_console_logs` for JS errors
3. **Check network**: Server may not be running
4. **Clear cookies**: Navigate away and back, or close browser

### Page Not Loading
**Problem**: Navigation times out or shows error

**Solutions**:
1. **Check server is running**: Look at terminal output
2. **Check port**: Confirm correct port (8000 for ACM2)
3. **Increase timeout**: Add `timeout` parameter to navigate
4. **Check for redirects**: May need to follow redirect chain

### CORS Errors
**Problem**: API calls blocked by CORS

**Solutions**:
1. **Use same origin**: Navigate browser to app first
2. **Check server CORS config**: Backend may need CORS middleware

---

## Known Issues and Solutions

### Issue: WordPress Submit Button Disabled ✅ SOLVED
**Symptom**: `playwright_click` on `#createusersub` times out with "element is not enabled"
**Cause**: WordPress disables submit button when password is "weak"
**Solution**: Click `.pw-checkbox` (Confirm use of weak password) before clicking submit

### Issue: WordPress REST API 401 for User Creation
**Symptom**: POST to `/wp-json/wp/v2/users` returns 401 "rest_cannot_create_user"
**Cause**: Cookie authentication doesn't work for REST API mutations
**Solution**: Use WordPress admin UI instead (Workflow 5), or set up Application Passwords

### Issue: Browser Already Open
**Symptom**: Error about existing browser session
**Solution**: Call `playwright_close` before starting new test

### Issue: Screenshot Returns Base64
**Symptom**: Can't see screenshot content
**Solution**: Use `savePng: true` and `downloadsDir` to save to disk

### Issue: Form Submission Doesn't Work
**Symptom**: Click on submit doesn't trigger form
**Solution**: Try `playwright_press_key` with "Enter" instead of click

### Issue: Dropdown Won't Select
**Symptom**: `playwright_select` fails
**Solution**: Check if it's a custom dropdown (not `<select>`), use click instead

### Issue: Page Content Not Updating
**Symptom**: Old content still visible after action
**Solution**: Add wait, or use `playwright_evaluate` to check for changes

---

## Testing Workflows

### Workflow 1: ACM2 Login Test
```
1. playwright_navigate: url="http://localhost:8000"
2. playwright_screenshot: name="login-page"
3. playwright_fill: selector="#username", value="testuser12"
4. playwright_fill: selector="#password", value="testuser12"
5. playwright_click: selector="button[type='submit']"
6. playwright_screenshot: name="after-login"
7. playwright_get_visible_text (verify dashboard content)
```

### Workflow 2: ACM2 API Test
```
1. playwright_post: url="http://localhost:8000/api/auth/login", value='{"username":"testuser12","password":"testuser12"}'
2. (extract token/key from response)
3. playwright_get: url="http://localhost:8000/api/presets" (with auth header)
```

### Workflow 3: WordPress Login Test ✅ VERIFIED
```
1. playwright_navigate: url="http://localhost/wordpress/wp-login.php"
2. playwright_fill: selector="#user_login", value="testuser12"
3. playwright_fill: selector="#user_pass", value="testuser12"
4. playwright_click: selector="#wp-submit"
5. playwright_screenshot: name="wp-dashboard"
```

### Workflow 5: WordPress Create User ✅ VERIFIED (Jan 11, 2026)
```
1. Login to WordPress (Workflow 3)
2. playwright_navigate: url="http://localhost/wordpress/wp-admin/user-new.php"
3. playwright_fill: selector="#user_login", value="newusername"
4. playwright_fill: selector="#email", value="newuser@example.com"
5. playwright_fill: selector="#pass1", value="password123"
6. playwright_select: selector="#role", value="administrator"  # or subscriber/editor/etc
7. playwright_click: selector=".pw-checkbox"  # REQUIRED for weak passwords!
8. playwright_click: selector="#createusersub"
9. playwright_screenshot: name="user-created"
# Success shows "New user created." message
```

**IMPORTANT for Workflow 5**: 
- The submit button `#createusersub` is DISABLED until password is valid
- If password is "weak", you MUST click `.pw-checkbox` to confirm
- Without clicking `.pw-checkbox`, the button stays disabled and click times out

### Workflow 4: End-to-End ACM2 Preset Creation
```
1. Login (Workflow 1)
2. playwright_click: selector=".add-preset-btn"
3. playwright_fill: selector="#preset-name", value="Test Preset"
4. playwright_fill: selector="#preset-prompt", value="You are a helpful assistant"
5. playwright_click: selector="button[type='submit']"
6. playwright_screenshot: name="preset-created"
7. Verify preset appears in list
```

---

## Selector Discovery Process

When you encounter a page and don't know the selectors:

1. **Get the HTML**:
   ```
   playwright_get_visible_html: selector="body", cleanHtml=true
   ```

2. **Look for**:
   - `id` attributes (most reliable): `#element-id`
   - `name` attributes: `[name="field"]`
   - Unique classes: `.specific-class`
   - Form elements: `input`, `button`, `select`

3. **Update this document** with discovered selectors!

---

## Debugging Checklist

When something doesn't work:

- [ ] Is the server running? (Check terminal)
- [ ] Did I close the previous browser? (`playwright_close`)
- [ ] Can I see the page? (`playwright_screenshot`)
- [ ] What does the HTML look like? (`playwright_get_visible_html`)
- [ ] Are there console errors? (`playwright_console_logs`)
- [ ] Am I using the right selector? (check alternatives)
- [ ] Is the element in an iframe? (use iframe tools)
- [ ] Did I wait long enough? (add delay)

---

## Notes Section

Add discoveries and learnings here during testing:

### January 11, 2026 - Architecture Fixes
- **Static files archived**: `app/static` moved to `app/static_archive` - frontend should be served by WordPress
- **Per-user preset naming**: New users now get preset named `{username} default preset`
- **API prefix corrected**: All endpoints use `/api/v1/` prefix
- Created user `newuser99` via POST `/api/v1/users` - got API key for testing

### January 11, 2026 - Initial Setup
- Document created
- ACM2 server runs on port 8000
- testuser12 exists with password testuser12 (user_id=10 in MySQL)
- WordPress path: C:\xampp\htdocs\wordpress
- WordPress URL: http://localhost/wordpress
- Successfully logged into WordPress as testuser12
- Successfully created user `apiuser1` via WordPress admin UI
- Discovered: WordPress REST API POST requires Application Passwords (cookies not enough)
- Discovered: WordPress weak password requires clicking `.pw-checkbox` or submit button stays disabled

---

## Remember

1. **Always screenshot** before and after critical actions
2. **Always check console logs** when something fails
3. **Always update this document** when you discover something new
4. **Always close browser** at end of test session
5. **Never assume selectors** - verify with get_visible_html first

================================================================================
FOREVER README - WordPress & Apache Configuration Changes
================================================================================
This file documents all changes made OUTSIDE the godzilla project folder.
Since WordPress and Apache configs are not version controlled with ACM2,
these changes must be manually recreated on any new installation.

Last Updated: January 9, 2026

================================================================================
1. WORDPRESS PLUGIN INSTALLATION
================================================================================
Location: C:\xampp\htdocs\wordpress\wp-content\plugins\acm2-integration\

The entire plugin folder must be copied to WordPress plugins directory.
Plugin files include:
  - acm2-integration.php (main plugin file)
  - includes/class-api-proxy.php (proxies requests to ACM2 backend)
  - includes/class-user-sync.php (syncs WP users to ACM2 on registration)
  - admin/class-settings-page.php (admin settings UI)
  - admin/class-provider-keys-page.php (provider keys management)
  - admin/class-react-app.php (embeds React app in WP page)
  - assets/react-build/ (compiled React app)

After copying, activate plugin in WordPress Admin > Plugins.

================================================================================
2. WORDPRESS DATABASE CHANGES
================================================================================
Database: acm2_wordpress (or your WordPress database name)

A. Custom Table Created (on plugin activation):
   Table: wp_acm2_api_keys
   Schema:
     - id bigint(20) AUTO_INCREMENT PRIMARY KEY
     - wp_user_id bigint(20) NOT NULL UNIQUE
     - acm2_api_key varchar(255) NOT NULL
     - created_at datetime DEFAULT CURRENT_TIMESTAMP
     - updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

B. Options Added (wp_options table):
   - acm2_api_url = 'http://127.0.0.1:8000/api/v1'
   - acm2_api_timeout = 30

To verify:
   SELECT * FROM wp_options WHERE option_name LIKE 'acm2%';

================================================================================
3. ACM2 MASTER DATABASE (MySQL)
================================================================================
Database: acm2_master

This is a SEPARATE MySQL database (not WordPress's database).

A. Create Database:
   CREATE DATABASE acm2_master
     CHARACTER SET utf8mb4
     COLLATE utf8mb4_unicode_ci;

B. Tables:
   
   users:
     - id INT AUTO_INCREMENT PRIMARY KEY
     - username VARCHAR(255) NOT NULL UNIQUE
     - email VARCHAR(255) NOT NULL UNIQUE
     - wordpress_user_id INT UNIQUE
     - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     - updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
   
   api_keys:
     - id INT AUTO_INCREMENT PRIMARY KEY
     - user_id INT NOT NULL (FK to users.id)
     - key_hash VARCHAR(255) NOT NULL UNIQUE
     - key_prefix VARCHAR(20) NOT NULL
     - name VARCHAR(255)
     - last_used_at TIMESTAMP NULL
     - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     - revoked_at TIMESTAMP NULL

Schema file: acm2/acm2/app/db/master_schema_mysql.sql

================================================================================
4. STANDARD PORT CONFIGURATION
================================================================================
ACM2 Backend Port: 8000 (PERMANENT - DO NOT CHANGE)

This port is configured in:
  - ACM2: cli.py (default serve port)
  - ACM2: app/main.py (uvicorn default)
  - WordPress: acm2-integration.php (default option value)
  - WordPress DB: wp_options.acm2_api_url

================================================================================
5. APACHE/XAMPP CONFIGURATION
================================================================================
No Apache config changes required for local development.

WordPress runs on Apache port 80 (default XAMPP).
ACM2 runs on uvicorn port 8000 (separate process).
WordPress plugin proxies requests from WP to ACM2.

For production, you may need:
  - ProxyPass rules to forward /acm2-api/ to localhost:8000
  - CORS headers if accessing ACM2 directly from browser

================================================================================
6. HOW USER SYNC WORKS
================================================================================
When a new WordPress user registers:
1. WordPress fires 'user_register' hook
2. ACM2_User_Sync::sync_new_user() is called
3. Plugin POSTs to http://127.0.0.1:8000/api/v1/users with:
   - username
   - email  
   - wordpress_user_id
4. ACM2 creates user in acm2_master.users table
5. ACM2 generates API key, returns it in response
6. Plugin saves API key to wp_acm2_api_keys table
7. User can now access ACM2 app with their key

================================================================================
7. TROUBLESHOOTING
================================================================================
If user creation fails:
  - Check ACM2 server is running on port 8000
  - Check wp_options.acm2_api_url is correct
  - Check PHP error logs for connection errors
  - Verify acm2_master database exists and is accessible

If React app shows empty (no presets/runs):
  - User may not have ACM2 account (check acm2_master.users)
  - API key may be missing (check wp_acm2_api_keys)
  - Use "Sync All Users" button in WP Admin to create missing accounts

================================================================================
END OF FOREVER README
================================================================================
MariaDB, WordPress, and XAMPP are bug-free.

If MySQL crashes, it's because our code sent a bad query, created a corrupted table, or misconfigured a connection.

If WordPress fails, it's because our plugin has a PHP error, a missing file, or a bad hook.

If Apache won't start, it's because our configuration is wrong.

All bugs are in our code. Period.

Write files using [System.Text.UTF8Encoding]::new($false) - the $false means "no BOM"