# FUCKING-LIVE-STAT-9-1: META REPORT

**Date**: December 20, 2025  
**Consolidation of**: FUCKING-LIVE-STATS 1-8  
**Project**: ACM2 (API Cost Multiplier 2.0)  
**Feature**: FPF Live Stats Subsystem

---

## EXECUTIVE SUMMARY

The Live Stats feature for ACM2's FilePromptForge (FPF) integration has been through **8 major debugging iterations** spanning December 19-20, 2025. What appeared to be a simple requirement—displaying real-time call counters in the UI—exposed a cascade of architectural failures, race conditions, and silent error handling.

### Final Status: ⚠️ PARTIALLY WORKING, FRAGILE

The core WebSocket broadcasting now functions, but significant reliability issues remain.

---

## CHRONOLOGICAL TIMELINE

### Report 1: Initial Incident Analysis
- **Focus**: Comprehensive 100-page technical analysis of the failure
- **Key Finding**: FPF's 3KB minimum output check rejected valid JSON responses (~381 bytes)
- **Symptom**: 2,016 redundant API calls in a single run due to infinite retry loops
- **Resolution**: Implemented `--json` flag to bypass size check

### Report 2: First Success
- **Date**: Dec 19, 2025 @ 21:14
- **Status**: ✅ FIXED AND WORKING
- **Key Finding**: Generation phase had NO stats tracking (only evaluation was tracked)
- **Root Cause**: Old .pyc cache meant server was running stale code
- **Resolution**: Added `record_call_start("generation")` and cleared cache

### Report 3: Frontend Wiring Investigation
- **Focus**: Predictions and test procedure for frontend integration
- **Key Findings**: 
  - WebSocket events updated React Query cache, but Execute.tsx read from local state
  - Polling overwrote `fpf_stats` with `null` from API
- **Test Result**: ❌ FAILED - Run ID mismatch discovered
- **Root Cause**: `RunExecutor` using stale `_current_run_id` from previous run

### Report 4: Comprehensive Fix Session
- **Duration**: ~2 hours
- **Cumulative Effort**: 6+ months, 1000+ attempted fixes
- **Final Fix**: WebSocket URL path mismatch
  - Frontend: `/ws/run/{id}`
  - Backend: `/api/v1/runs/ws/run/{id}`
- **Resolution**: ✅ LIVE STATS WORKING at 9:50 PM

### Report 5: UI/UX Bug Catalog
- **Focus**: Execute page improvements
- **13 bugs identified** including:
  - Duration display showing double format
  - Evaluation scores not streaming live
  - Stats not persisting across refresh
  - 0/0 evaluations counter
  - White-on-white text
  - FPF HTTP retry loop with no total deadline (30-min worst case)
  - Retries NOT reflected in Live Stats

### Report 6: Partial Resolution Status
- **Fixed**:
  1. "Output Too Small" loop (--json flag)
  2. "Silent Failure" of stats (closure fix)
  3. 30-minute timeout (configurable GUI timeout)
- **Still Broken**:
  - No stats on page refresh
  - Duration display glitch
  - 0/0 evaluations counter
  - White-on-white text

### Report 7: Postmortem (Dec 20)
- **Run IDs**: ACM 066d07f9, FPF 5536f75b
- **Problems Observed**:
  - 0 connected WebSocket clients for ALL stats updates
  - Stale error text persisted after successful calls
  - `parsed_json_found=False` despite --json flag
  - Heartbeats reached 800-1170s with uneven intervals
  - Phase transitions delayed and not synchronized

### Report 8: Stuck Pipeline Analysis
- **Run**: 066d07f9-96e5-4f2f-996d-78b66c493072
- **Problem**: Heartbeats reached 1172s despite 600s configured timeout
- **Root Cause**: Timeout not enforced by scheduler
- **Missing**: FPF artifact for in-flight run (no *.json produced)
- **Impact**: No cancel/cleanup, no completion record

---

## ROOT CAUSES IDENTIFIED (ALL 8 REPORTS)

| # | Root Cause | Report | Status |
|---|------------|--------|--------|
| 1 | 3KB minimum output check vs 381-byte JSON | 1 | ✅ Fixed (--json flag) |
| 2 | Generation phase not tracked | 2 | ✅ Fixed |
| 3 | .pyc cache serving stale code | 2 | ✅ Fixed |
| 4 | Judge creating NEW FpfStatsTracker instead of using passed one | 4 | ✅ Fixed |
| 5 | Exception swallowing in `_notify()` | 4 | ✅ Fixed |
| 6 | Run ID mismatch (stale `_current_run_id`) | 3, 4 | ✅ Fixed |
| 7 | WebSocket URL path mismatch | 4 | ✅ Fixed |
| 8 | WebSocket race condition (broadcast before connect) | 4, 7 | ⚠️ Mitigated (500ms delay) |
| 9 | Stats not persisted to DB during run | 5, 6, 7 | ❌ NOT FIXED |
| 10 | FPF HTTP retry loop has no total deadline | 5 | ❌ NOT FIXED |
| 11 | Retries not reflected in Live Stats | 5 | ❌ NOT FIXED |
| 12 | Timeout not enforced by scheduler | 8 | ❌ NOT FIXED |
| 13 | Stale error text not cleared on recovery | 7 | ❌ NOT FIXED |
| 14 | Phase transitions delayed | 7 | ❌ NOT FIXED |

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXECUTE PAGE (React)                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │
│  │ FPF Live Stats │  │ Timeline       │  │ Console Logs           │ │
│  │ 5 OK / 1 Fail  │  │ [Doc evaluations]│ │ [Streaming log output] │ │
│  └───────▲────────┘  └────────────────┘  └────────────────────────┘ │
│          │                                                           │
│          │ WebSocket: fpf_stats_update                               │
└──────────┼───────────────────────────────────────────────────────────┘
           │
┌──────────┴───────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI + Uvicorn)                       │
│                                                                       │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│  │ RunExecutor     │───▶│ FpfStatsTracker │───▶│ WebSocket Mgr   │   │
│  │ - execute()     │    │ - counters      │    │ - broadcast()   │   │
│  │ - _broadcast()  │    │ - _on_update    │    │ - connections   │   │
│  └────────┬────────┘    └─────────────────┘    └─────────────────┘   │
│           │                                                           │
│           ▼                                                           │
│  ┌─────────────────┐    ┌─────────────────┐                          │
│  │ Judge           │───▶│ FPF Subprocess  │                          │
│  │ - evaluate()    │    │ (CLI)           │                          │
│  └─────────────────┘    └─────────────────┘                          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## KEY METRICS

| Metric | Value |
|--------|-------|
| Debug sessions | 8 |
| Days spent | 2 (Dec 19-20, 2025) |
| Distinct root causes found | 14 |
| Root causes fixed | 8 |
| Root causes remaining | 6 |
| Run IDs analyzed | 10+ |
| API calls wasted (worst incident) | 2,016 |
| Longest stuck run | 1,172 seconds (19.5 minutes) |

---

## MODEL PERFORMANCE COMPARISON

| Model | Typical Time | Notes |
|-------|--------------|-------|
| google:gemini-2.5-flash | 15-25s | Fast, includes web search |
| google:gemini-2.5-pro | 40-60s | Slower but more capable |
| openai:gpt-5.1 | 200s+ | Multiple web searches |
| openai:gpt-5-mini | 200-300s | Very slow (reasoning + web search) |

---

## CRITICAL REMAINING ISSUES

### 1. Stats Not Persisted (HIGH)
**Impact**: Page refresh loses all progress visibility  
**Fix**: Write stats to DB periodically during run

### 2. HTTP Retry No Deadline (HIGH)
**Impact**: Single API call can take 30 minutes (600s × 3 retries)  
**Fix**: Add `deadline` parameter to `_http_post_json()`

### 3. Timeout Not Enforced (HIGH)
**Impact**: Runs exceed configured timeout without cancellation  
**Fix**: Scheduler must kill subprocess when timeout exceeded

### 4. Retries Invisible (MEDIUM)
**Impact**: UI shows `retries: 0` while FPF is actually retrying  
**Fix**: Parse FPF stderr or emit structured retry events

### 5. Stale Error State (MEDIUM)
**Impact**: UI shows error even after recovery  
**Fix**: Clear `last_error` on successful call

### 6. WebSocket Race Condition (MEDIUM)
**Impact**: First stat update may be missed  
**Fix**: Wait for WebSocket `onopen` before calling `/start`

---

## FILES INVOLVED

| Purpose | Path |
|---------|------|
| Run orchestration | `app/services/run_executor.py` |
| Stats tracking | `app/evaluation/__init__.py` |
| WebSocket manager | `app/api/websockets.py` |
| Judge (evals) | `app/evaluation/judge.py` |
| FPF adapter | `app/adapters/fpf/adapter.py` |
| FPF file handler | `FilePromptForge/file_handler.py` |
| React WebSocket hook | `ui/src/hooks/useRunSocket.ts` |
| Execute page | `ui/src/pages/Execute.tsx` |
| Database models | `app/infra/db/models.py` |

---

## LESSONS LEARNED

1. **Never swallow exceptions silently** - The `try/except: pass` pattern hid the real errors for hours.

2. **Closures capture by reference** - The run ID mismatch was caused by `self._current_run_id` being evaluated at callback time, not at creation time.

3. **WebSocket paths must match exactly** - A missing `/api/v1/runs` prefix broke the entire feature.

4. **Race conditions are subtle** - The frontend can't assume the WebSocket is connected after `setState()` returns.

5. **Subprocess timeouts need enforcement** - Configuring a timeout doesn't mean it's enforced—the scheduler must actively kill stalled processes.

6. **Retry loops compound** - HTTP-level retries × FPF-level retries = exponential worst-case timing.

7. **In-memory state is ephemeral** - If stats aren't persisted, they're lost on refresh.

8. **Clear Python cache after edits** - `.pyc` files can serve stale code even after source changes.

---

## RECOMMENDATIONS

### Immediate (This Week)
1. Persist `fpf_stats` to DB every 5 seconds during run
2. Add total deadline to FPF HTTP retry loop
3. Enforce timeout in RunExecutor scheduler
4. Clear `last_error` on successful call recovery

### Short-Term (This Month)
1. Implement proper WebSocket connection waiting (await `onopen`)
2. Parse FPF stderr for retry events
3. Fix all UI/UX bugs from Report 5

### Long-Term (Next Quarter)
1. Consider replacing WebSocket with Server-Sent Events (simpler)
2. Add structured event emission from FPF subprocess
3. Implement comprehensive integration tests for the full pipeline

---

## CONCLUSION

The Live Stats feature went from "completely broken" to "mostly working" over 8 debugging sessions. The core data flow now functions: counters increment, WebSocket broadcasts, and the UI updates. However, the system remains fragile due to missing persistence, unenforced timeouts, and invisible subprocess retries.

**Next Priority**: Fix stats persistence to survive page refresh, then address the timeout enforcement bug.

---

*End of Meta Report*
