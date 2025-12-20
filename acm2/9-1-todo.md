# ACM2 Live Stats TODO List

**Extracted from**: FUCKING-LIVE-STATS 1-8  
**Date**: December 20, 2025

---

## 🔴 CRITICAL (Must Fix)

### 1. Persist Live Stats to Database
- **Source**: Reports 5, 6, 7
- **Problem**: FPF stats are in-memory only; page refresh shows "No stats"
- **File**: `app/services/run_executor.py`
- **Fix**: Modify `_broadcast_stats` to also update `fpf_stats` column in DB every 5 seconds
- **Acceptance**: Refreshing page during run shows current stats

### 2. FPF HTTP Retry Loop Total Deadline
- **Source**: Report 5
- **Problem**: HTTP retry loop has no total deadline; 600s × 3 = 1800s worst case per call
- **File**: `FilePromptForge/file_handler.py` (line ~119)
- **Fix**: Add `deadline` parameter to `_http_post_json()`
```python
def _http_post_json(url, payload, headers, timeout=600, max_retries=3, deadline=None):
    for attempt in range(1, max_retries + 1):
        if deadline and time.time() > deadline:
            raise RuntimeError("Total execution deadline exceeded")
```
- **Acceptance**: Single call cannot exceed configured deadline regardless of retries

### 3. Enforce Timeout in Scheduler
- **Source**: Report 8
- **Problem**: Heartbeat reached 1172s despite 600s configured timeout
- **File**: `app/services/run_executor.py` or scheduler component
- **Fix**: Kill subprocess when elapsed time > configured timeout
- **Acceptance**: Runs fail cleanly when timeout exceeded

### 4. Reflect FPF Retries in Live Stats
- **Source**: Reports 5, 7
- **Problem**: Live Stats shows `retries: 0` while FPF logs show retries happening
- **Files**: `app/adapters/fpf/adapter.py`, `app/evaluation/__init__.py`
- **Fix Options**:
  1. Parse FPF stderr for retry patterns (`Transient error on attempt X/Y`)
  2. Have FPF emit structured retry events that ACM captures
- **Acceptance**: Live Stats retry count matches FPF log entries

---

## 🟠 HIGH (Should Fix)

### 5. Clear Stale Error on Recovery
- **Source**: Report 7
- **Problem**: `last_error` stays set even after successful calls
- **File**: `app/evaluation/__init__.py` (FpfStatsTracker)
- **Fix**: In `record_success()`, set `self.last_error = None`
- **Acceptance**: UI error indicator clears when calls succeed

### 6. Evaluations Counter Shows 0/0
- **Source**: Reports 5, 6
- **Problem**: Evaluations info box always displays "0 / 0"
- **Files**: `app/services/run_executor.py`, `ui/src/pages/Execute.tsx`
- **Fix**: Calculate `total_evaluations = docs × models × eval_types` and send in init message
- **Acceptance**: Counter shows `3 / 12` format during run

### 7. Single Evaluation Scores Should Stream Live
- **Source**: Report 5
- **Problem**: Scores only appear after ALL evaluations complete
- **Files**: `app/api/websockets.py`, `ui/src/pages/Execute.tsx`
- **Fix**: Emit `evaluation_complete` WebSocket event after each eval, not just at end
- **Acceptance**: Timeline shows each score as soon as evaluation completes

### 8. WebSocket Race Condition
- **Source**: Reports 4, 7
- **Problem**: Backend broadcasts before frontend WebSocket connects (0 connections)
- **File**: `ui/src/pages/Execute.tsx`
- **Current Mitigation**: 500ms delay
- **Better Fix**: Wait for WebSocket `onopen` before calling `/start`
```typescript
const ws = new WebSocket(url);
await new Promise(resolve => { ws.onopen = resolve; });
// Then call /start
```
- **Acceptance**: First stat update is never missed

---

## 🟡 MEDIUM (Should Fix When Time Permits)

### 9. Duration Display Bug
- **Source**: Reports 5, 6
- **Problem**: Shows "05:46:09 - —" instead of single elapsed time
- **File**: `ui/src/pages/Execute.tsx`
- **Fix**: Handle null end time gracefully; show "Running: 5m 30s"
- **Acceptance**: Single, clear duration format

### 10. White on White Text
- **Source**: Reports 5, 6
- **Problem**: Evaluation details in Timeline tab are unreadable
- **File**: UI CSS for evaluation detail cards
- **Fix**: Add proper text color for light background
- **Acceptance**: All text is readable

### 11. Remove Decimal Seconds
- **Source**: Report 5
- **Problem**: Times show "12.345s" instead of "12s"
- **File**: Time formatting utility functions
- **Fix**: Add `Math.round()` to all duration displays
- **Acceptance**: All times display as whole seconds

### 12. Page/Console Jerks on Log Write
- **Source**: Report 5
- **Problem**: Page jumps when new log entries are written
- **File**: Console/log component
- **Fix**: Stable height with `overflow: auto`, conditional auto-scroll
- **Acceptance**: User scroll position preserved unless at bottom

### 13. Phase Transition Sync
- **Source**: Report 7
- **Problem**: Stats show "current_phase=generation" long after phase ended
- **File**: `app/services/run_executor.py`
- **Fix**: Emit phase change event at actual task boundaries
- **Acceptance**: Phase indicator matches actual current operation

---

## 🟢 LOW (Nice to Have)

### 14. Build Preset Page Default
- **Source**: Report 5
- **Problem**: Page starts empty instead of loading Default Preset
- **File**: `ui/src/pages/BuildPreset.tsx`
- **Fix**: Load Default Preset in `useEffect`
- **Acceptance**: Page opens with Default Preset populated

### 15. Remove FPF Output Tab
- **Source**: Report 5
- **Problem**: Unnecessary tab on Execute page
- **File**: `ui/src/pages/Execute.tsx`
- **Fix**: Delete the tab component
- **Acceptance**: Tab no longer appears

### 16. Verify Stats Accuracy
- **Source**: Report 5
- **Problem**: Unknown if failed_calls and retries counts are accurate
- **Test Required**: Run execution with known failures, compare stats to logs
- **File**: `app/evaluation/judge.py`
- **Acceptance**: Stats match log entries exactly

---

## 📊 INVESTIGATION ITEMS

### 17. Missing FPF Artifact for Stuck Runs
- **Source**: Report 8
- **Problem**: Stuck run (1cad298e) never produced *.json log
- **Investigation**: Why did FPF subprocess not write consolidated log?
- **Impact**: Cannot debug API calls for stuck runs

### 18. Heartbeat Math Issues
- **Source**: Reports 7, 8
- **Problem**: Heartbeat elapsed values (800-1170s) and uneven intervals
- **Investigation**: Is the heartbeat calculation wrong or duplicated?
- **Impact**: Hard to tell real wall-clock progress

---

## PRIORITY MATRIX

| Priority | Count | Examples |
|----------|-------|----------|
| 🔴 CRITICAL | 4 | Persist stats, HTTP deadline, timeout enforcement, retry visibility |
| 🟠 HIGH | 4 | Clear error, eval counter, stream scores, WS race |
| 🟡 MEDIUM | 5 | Duration, white text, decimals, jerking, phase sync |
| 🟢 LOW | 3 | Default preset, remove tab, verify accuracy |
| 📊 INVESTIGATE | 2 | Missing artifact, heartbeat math |

---

## SUGGESTED ORDER OF IMPLEMENTATION

### Week 1
1. ✅ Persist Live Stats to DB (Critical #1)
2. ✅ Enforce Timeout in Scheduler (Critical #3)
3. ✅ Clear Stale Error on Recovery (High #5)

### Week 2
4. ✅ Evaluations Counter (High #6)
5. ✅ Duration Display Bug (Medium #9)
6. ✅ White on White Text (Medium #10)

### Week 3
7. ✅ FPF HTTP Retry Total Deadline (Critical #2)
8. ✅ Stream Eval Scores Live (High #7)
9. ✅ WebSocket Race Condition (High #8)

### Week 4
10. ✅ Reflect FPF Retries (Critical #4)
11. ✅ Remaining Medium/Low items

---

## FILES TO MODIFY

| File | Items |
|------|-------|
| `app/services/run_executor.py` | #1, #3, #6, #13 |
| `app/evaluation/__init__.py` | #4, #5 |
| `FilePromptForge/file_handler.py` | #2 |
| `app/adapters/fpf/adapter.py` | #4 |
| `ui/src/pages/Execute.tsx` | #7, #8, #9, #12, #15 |
| `ui/src/hooks/useRunSocket.ts` | #8 |
| `ui/src/pages/BuildPreset.tsx` | #14 |
| CSS files | #10, #11 |

---

*Generated from FUCKING-LIVE-STATS reports 1-8*
