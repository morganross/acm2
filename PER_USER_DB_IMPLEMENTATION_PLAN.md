# Per-User DB Implementation Proposal

## Clarification on item 3
“Run seeding in a background job” means: create the user immediately, then enqueue a separate task that builds the user’s database (copy preset + content + one historical run). This keeps user creation fast and avoids timeouts or partial failures. The task can retry safely if anything fails.

---

## Goals
- Each new user gets a fully functional per-user DB on creation.
- Seed exactly one specific historical run with full generated documents, scores, and reports so Evaluation tabs render correctly.
- Per-user DB remains the core data model.
- File storage is per-user and deterministic (no global paths).
- API access to files is enforced by DB ownership + per-user file root.
- Seeding is repeatable, versioned, and safe.
- UI must not load user data until the DB is fully populated.

---

## Proposed Architecture
### 1) Seed Package (Versioned)
- Define a canonical “seed package” with:
  - One preset (default)
  - Full content library
  - One specific historical run (complete, with documents, artifacts, eval results, and reports)
  - The full file tree for that run (generated docs, logs, reports)
- Tag this package with a version (e.g., v1, v2) for deterministic seeding.
- The seed package is the source of truth for new-user data.
- Configure the seed package explicitly via environment:
  - `SEED_PRESET_ID`
  - `SEED_RUN_ID`
  - `SEED_VERSION`

### 2) Per-User DB + File Initialization Flow
1. Create user in master DB.
2. Create per-user SQLite DB file.
3. Run migrations to create schema.
4. Copy per-user file root from seed package (fast file copy).
5. Seed per-user DB from seed package.
6. Mark user’s DB as “ready”.
7. UI/API blocks until readiness is true.

### 3) Seeding Strategy
- Copy from a known source DB (seed package) into the target user DB.
- Maintain an ID mapping table for:
  - content IDs
  - preset IDs
  - run IDs
  - document IDs
  - artifact IDs
- Rewrite foreign keys and references during copy.
- Copy the run’s file tree into a per-user file root.
- Keep run_id consistent between DB and file tree to avoid mismatches.

### 4) Historical Run Requirements
- Must include:
  - run record
  - all generated documents
  - eval outputs (scores + pairwise)
  - artifacts
  - reports
  - any references to content IDs or preset IDs
- Ensure all these references are rewritten to the new per-user IDs.
- Ensure file paths resolve under the per-user file root.

---

## Implementation Steps
1. **Define seed package**
  - Identify the exact preset, content list, and run ID to copy.
  - Freeze that data in a dedicated seed DB and a seed file tree bundle.
  - ✅ Implemented explicit seed package config in environment (SEED_PRESET_ID/SEED_RUN_ID/SEED_VERSION).

2. **Add a seed version marker**
  - Store a `seed_version` in per-user DB metadata.
  - Prevent re-seeding if already applied.
  - Fail initialization if seed package IDs/version are missing.
  - ✅ Implemented `user_meta` table with `seed_status` + `seed_version`.

3. **Build ID-mapping copier**
  - Copy tables in safe order:
    1) content
    2) preset
    3) run
    4) documents
    5) artifacts
  - Rewrite references as data is copied.
  - ✅ Implemented ID remap and deep replacement in run config/results.

4. **Implement per-user file root**
  - Define deterministic base paths:
    - `data/user_{id}/runs/{run_id}/generated/`
    - `data/user_{id}/runs/{run_id}/logs/`
    - `data/user_{id}/runs/{run_id}/reports/`
  - Copy the seed run’s file tree into that per-user path.
  - Ensure report generation and generated-doc lookups resolve using user_id + run_id.
  - ✅ Implemented per-user file root for reads/writes and seed file copy to per-user run root.

5. **Enforce ownership for file access**
  - API must load the run from the user’s DB first.
  - File paths are always derived from user_id + run_id.
  - No global `logs/{run_id}` access.
  - ✅ Implemented per-user file root derivation in run artifacts and logging.

6. **Integrate into user creation**
  - Create user → seed synchronously (fast file copy + DB insert).
  - Mark `seed_status=ready` only when both DB + files are present.
  - ✅ Implemented synchronous seeding + `seed_status` updates.

7. **Readiness gate**
  - If `seed_status != ready`, API returns “setup in progress”.
  - UI blocks until readiness is true.
  - ✅ Implemented backend readiness gate + UI block screen.

8. **Validation checks**
  - Confirm all expected records exist in per-user DB.
  - Confirm file paths exist under the per-user root.
  - Verify the seeded run renders in Evaluation tabs.
  - Run backfill for existing users (seed status + metadata).
  - ⏳ Backfill pending (requires MySQL up).

---

## Current Progress (Jan 15, 2026)
- ✅ Per-user file root enforced for read/write paths.
- ✅ Seed package required via env (`SEED_PRESET_ID`, `SEED_RUN_ID`, `SEED_VERSION`).
- ✅ Seed copies: preset + referenced content + run + documents + tasks + artifacts + file tree.
- ✅ Readiness gate implemented (API + UI).
- ✅ `/users/me` returns `seed_status`.
- ✅ Backfill script created.

## Current Blockers
- Backfill failed because MySQL is not running.
- Seed run files must include reports; currently only `generated/` and `run.log` exist under the selected run.

## Next Steps
1) Start MySQL service.
2) Run backfill: `python -m app.db.backfill_user_meta` from `acm2/acm2`.
3) Confirm seed run file tree includes reports; if not, generate reports for the seed run and re-copy.

---

## Risks & Mitigations
- **Large run data**: seed only one canonical run; avoid copying many runs.
- **Reference mismatch**: use strict ID mapping + validation.
- **Missing files**: copy full run file tree during seeding; validate file presence.
- **Partial seed**: gate UI until both DB + files exist.

---

## Acceptance Criteria
- New user sees:
  - One default preset
  - Full content library
  - One historical run that renders Evaluation tabs correctly
  - Generated documents and reports render successfully
- API blocks until the user’s DB + files are ready.
- No cross-user data leakage (DB or files).
- Seeding is repeatable and versioned.

---

## Front-End Refactor Instructions (Per-User DB + Files)
1. **Use a single API client everywhere**
  - Replace raw `fetch('/api/v1/...')` calls with the shared client in all pages.
  - This ensures all requests carry the same auth headers.

2. **Send the correct auth header**
  - Backend expects `X-ACM2-API-Key` for per-user DB resolution.
  - Ensure every request uses that header (not Authorization/Bearer).

3. **Fix WebSocket authentication**
  - Run updates must be per-user. Add API key via query param or subprotocol.
  - Without this, per-user isolation is bypassed for live updates.

4. **Handle report download securely**
  - `window.open` can’t attach headers.
  - Use a server-side proxy route or signed URL so auth is enforced.

5. **UI readiness gate**
  - If `seed_status != ready`, block the UI with a “setup in progress” screen.
  - Do not fetch presets/runs until ready is true.

6. **API base URL consistency**
  - Dev base URL currently points to port 8002; confirm correct port.
  - Keep base URL config in one place (the shared client).

---

## Missing Items / Open Gaps
1. **File storage remains global today**
  - Current API reads generated docs from `logs/{run_id}/...`.
  - Must move to per-user file root and derive path from user_id + run_id.

2. **Report generation depends on file paths**
  - Ensure report generator uses per-user file root.

3. **Auth mismatch in UI**
  - UI uses Authorization Bearer but backend expects X-ACM2-API-Key.

4. **WebSocket auth missing**
  - Live run updates can leak cross-user data without auth.

5. **Seeded historical run must include full file tree**
  - DB rows alone are insufficient; generated docs/logs/reports must be copied.
---

## Questionable Design Decisions (Jan 15, 2026 Audit)

1. **Documents keep original IDs**
   - While this simplifies the copier, it means document IDs are shared between users if they have the same seed.
   - Works but feels leaky. A consistent "remap everything" approach would be cleaner.
   - **Decision: Keep as-is** - Documents are immutable input content; no security risk.

2. **Run ID is also not remapped** ✅ REMOVED
  - Historical run seeding has been removed entirely.

3. **No rollback of files on DB failure** ✅ REMOVED
  - Historical run file copy removed, so this is no longer applicable.

---

## Missing Pieces (Jan 15, 2026 Audit)

1. **No WebSocket auth** ✅ FIXED
   - Both WebSocket endpoints now require `api_key` query parameter:
     - `/runs/ws/run/{run_id}?api_key=...` (already had it)
     - `/generation/ws/{task_id}?api_key=...` (added)

2. **Report download auth** ✅ ALREADY IMPLEMENTED
   - `/runs/{run_id}/report` endpoint uses `Depends(get_current_user)` + `Depends(get_user_db)`.
   - Returns `FileResponse` after auth validation.
   - Frontend should use `apiClient.get()` with blob response, not `window.open()`.

3. **Per-user file root for ALL file access** ✅ FIXED
  - Created `app/utils/paths.py` with canonical path helpers.
  - Fixed `evaluation.py` - was using global `Path("logs")`, now uses `get_user_run_path()`.
  - Fixed `execution.py` - was using global `Path("logs")`, now uses `get_fpf_log_path()`.
  - `artifacts.py` already used per-user paths via `get_run_root()`.
