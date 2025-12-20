# REPEATING PROBLEM: GUI Failure Analysis - Presets Not Displaying

## Executive Summary
The "Execute" page failing to list presets was caused by **two issues**: 
1. A **JavaScript bug** in the API client's URL construction that silently failed in production mode
2. A **port mismatch** between the frontend config and backend default

The backend API and database were functioning correctly throughout.

---

## Update: December 7, 2025 - ROOT CAUSE FOUND AND FIXED

### The Actual Bug: `new URL()` with Relative Path

**Location**: `acm2/ui/src/api/client.ts`, line 36

**The Problem**: The `attachParams` function used `new URL(relativePath)` which **throws an error** when the path is relative:

```javascript
// BROKEN CODE (production mode):
const url = new URL(`${API_BASE}${endpoint}`)  // API_BASE = "/api/v1"
// Results in: new URL("/api/v1/presets") → TypeError: Invalid URL
```

In JavaScript, `new URL("/api/v1/presets")` without a base URL throws "Invalid URL" because relative URLs require either:
- An absolute URL string, OR  
- A second parameter specifying the base URL

**Why it worked in dev mode**: In dev mode (ports 5173/5174), `API_BASE` was set to the absolute URL `http://127.0.0.1:8002/api/v1`, so `new URL()` worked fine.

**Why it failed in production mode**: In production mode (port 8002), `API_BASE` was the relative path `/api/v1`, causing `new URL()` to throw an error that was **silently swallowed** by the try/catch in the API call.

### The Fix Applied

```javascript
// FIXED CODE:
const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
```

By adding `window.location.origin` as the second parameter, relative URLs now work correctly.

### Additional Fix: Port Mismatch

**Location**: `acm2/app/main.py`, line 163

The `main.py` was configured to run on port **8000**, but:
- The frontend expected port **8002**
- The CLI defaults to port **8002**

Changed: `uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)`

---

## Previous Analysis (Still Valid Context)

## Diagnostic Findings

### 1. Backend Integrity (Confirmed)
- **Database**: The SQLite database (`~/.acm2/acm2.db`) correctly contains the "Default Preset" and other user-created presets.
- **API Endpoint**: A direct query to `http://127.0.0.1:8002/api/v1/presets` returns the expected JSON list of presets, including the new "Default Preset".
- **Server Configuration**: The server is correctly bound to `127.0.0.1:8002` and listening for requests.

### 2. Frontend Source Code (Verified)
- **Logic**: The `Execute.tsx` component correctly implements the `useEffect` hook to fetch presets on mount.
- **API Client**: The `client.ts` correctly handles the API base URL logic (`/api/v1` when served from the backend).
- **Data Models**: The TypeScript interfaces match the Pydantic schemas from the backend.

### 3. The Root Cause: ~~Stale Static Assets~~ **JavaScript URL Construction Bug**

~~The `acm2 serve` command serves the frontend from the `acm2/app/static` directory. This directory contains the **compiled build artifacts** of the frontend.~~

The actual root cause was a subtle JavaScript bug where `new URL()` was called with a relative path but no base URL, causing silent failures in production mode only.

## Resolution Plan

### Files Changed (December 7, 2025)

1. **`acm2/ui/src/api/client.ts`** - Fixed URL construction:
   ```javascript
   // Line 36: Added window.location.origin as base URL
   const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
   ```

2. **`acm2/app/main.py`** - Fixed port:
   ```python
   # Line 163: Changed port from 8000 to 8002
   uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
   ```

3. **`acm2/ui/src/pages/Execute.tsx`** - Fixed TypeScript warnings:
   ```typescript
   // Lines 44, 50: Prefixed unused parameters with underscore
   function generateEvalGridFromSummary(_preset: PresetSummary): EvalCell[] {
   function generatePairwiseGridFromSummary(_preset: PresetSummary): PairwiseCell[] {
   ```

### After Making Changes

Always rebuild the frontend after source changes:
```powershell
cd acm2/ui
npm run build
Copy-Item -Recurse -Force .\dist\* ..\app\static\
```

### Option A: Development Mode (Recommended for Coding)
Do not rely on `acm2 serve` to serve the frontend while developing. Instead:
1.  Run the backend: `acm2 serve` (Port 8002)
2.  Run the frontend: `cd ui; npm run dev` (Port 5173)
3.  Access the app at `http://localhost:5173`. This will always use the latest source code.

### Option B: Production Build (Fixing the "Serve" Command)
If you want `acm2 serve` to show the latest version:
1.  Navigate to the UI folder: `cd acm2/ui`
2.  Install dependencies (if needed): `npm install`
3.  Build the frontend: `npm run build`
4.  Copy the artifacts:
    *   **Windows (PowerShell)**: `Copy-Item -Recurse -Force .\dist\* ..\app\static\`
    *   **Linux/Mac**: `cp -r dist/* ../app/static/`

## Key Lesson Learned

**Silent JavaScript errors are dangerous.** The `new URL()` error was caught by a try/catch block in the API client, so no error appeared in the console. The presets simply never loaded, making it appear like a backend or data issue.

**Testing tip**: When debugging API issues, check the browser's Network tab to see if the request is even being made. In this case, the request was never sent because the URL construction failed before `fetch()` was called.

