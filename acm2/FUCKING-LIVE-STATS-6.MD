# LIVE STATS STATUS REPORT (FUCKING-LIVE-STATS-6.MD)

**Date**: December 19, 2025
**Status**: PARTIALLY RESOLVED / CRITICAL ISSUES REMAIN

---

## 1. THE CURRENT SITUATION

We have successfully identified and fixed several critical issues plaguing the live stats and execution pipeline, but significant "failings" remain that prevent a truly robust experience.

### ✅ WHAT IS FIXED
1. **The "Output Too Small" Loop**: Fixed by adding the `--json` flag to evaluation tasks. This prevents FPF from rejecting valid small JSON responses (300-500 bytes) as "too short" (minimum was 3KB).
2. **The "Silent Failure" of Stats**: We identified that `FpfStatsTracker` callbacks were being lost or not properly bound. The fix involved creating a closure in `RunExecutor` to capture the `run_id` and ensure the callback persists.
3. **The 30-Minute Timeout**: We discovered that `gpt-5-mini` generation tasks (which don't use `--json`) were hitting the default 600s timeout 3 times in a row (1800s total). We implemented a configurable timeout in the GUI that overrides the default, allowing these long-running tasks to complete.

### ❌ THE FAILINGS (CURRENT ISSUES)

#### A. The "No Stats on Refresh" Problem
**Severity**: HIGH
**Description**: If you refresh the page during a run, the "Live Stats" box resets to "No stats available" or zero.
**Root Cause**: The `FpfStatsTracker` is an in-memory object attached to the `RunExecutor` instance. It is NOT persisted to the database during the run. When the page reloads, it fetches the *static* run state from the DB, which doesn't contain the transient live stats until the run completes and saves them.
**Impact**: Users cannot monitor long-running jobs if they navigate away or refresh.

#### B. The "Duration Display" Glitch
**Severity**: MEDIUM
**Description**: The duration field often shows a confusing double format like "05:46:09 - —".
**Root Cause**: Frontend rendering logic likely tries to show "Start - End" but fails when "End" is null (running), resulting in a broken string.

#### C. The "0/0 Evaluations" Counter
**Severity**: MEDIUM
**Description**: The "Evaluations" counter often stays at "0 / 0" even when evaluations are happening.
**Root Cause**: The total expected evaluations count is not being correctly calculated or passed to the frontend. It requires multiplying (docs × models × iterations), which might be missing from the initial run config sent to the UI.

#### D. The "White on White" Text
**Severity**: LOW (Visual)
**Description**: In the "Timeline & Details" tab, evaluation details are unreadable (white text on white background).
**Root Cause**: CSS class collision or missing dark mode style for that specific card component.

#### E. The "Decimal Seconds" Clutter
**Severity**: LOW (Visual)
**Description**: Times are shown with unnecessary precision (e.g., "12.345s").
**Root Cause**: Missing `Math.round()` or integer formatting in the frontend time display helpers.

---

## 2. IMMEDIATE ACTION PLAN

To address the remaining failings, we must prioritize **Persistence** and **Frontend Polish**.

### STEP 1: Persist Live Stats (Fixing "No Stats on Refresh")
- **Plan**: Modify `RunExecutor._broadcast_stats` to *also* update a `live_stats` column (or JSON field) in the `runs` database table periodically (e.g., every 5 seconds or on significant changes).
- **Benefit**: When the UI loads, it can fetch the latest persisted stats from the DB instead of relying solely on the WebSocket stream.

### STEP 2: Fix Frontend Glitches
- **Duration**: Rewrite the duration formatter to handle `null` end times gracefully (e.g., just show "Running: 5m 30s").
- **Evaluations Counter**: Ensure the `total_evaluations` is calculated in `RunExecutor` initialization and sent in the `init` WebSocket message.
- **CSS**: Fix the text color for evaluation cards.

### STEP 3: Verify Timeout Configuration
- **Plan**: Double-check that the new GUI-based timeout setting is actually being respected by *all* task types (Generation, Single Eval, Pairwise Eval).
- **Benefit**: Prevents future "silent 30-minute failures".

---

## 3. CONCLUSION

The system is functional but fragile. The backend execution logic is now sound (timeouts, flags, retries), but the **observability** (Live Stats) is ephemeral and the **user experience** (UI glitches) is unpolished. We are moving from "System Failure" mode to "User Experience Improvement" mode.
