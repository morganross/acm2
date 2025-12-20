# Execute Page Bug Fixes & Improvements

**Created**: December 19, 2025  
**Status**: Investigation & Implementation Required

---

## TODO List

### 1. Duration Display Bug
**Problem**: Duration field shows two times instead of one (e.g., "05:46:09 - —")  
**Expected Behavior**: 
- While running: Show elapsed time since run started (single value, updating live)
- After completion: Show total elapsed time from start to finish (single value, static)
**Investigation**: Find where duration is rendered and fix the format logic

---

### 2. Single Evaluation Scores Should Stream Live
**Problem**: Evaluation scores only appear after ALL evaluations complete  
**Expected Behavior**: Each evaluation result should appear in the UI immediately upon individual completion  
**Investigation**: Check how evaluation results are sent via WebSocket and rendered in the UI timeline

---

### 3. Live Stats Must Persist Across Page Refresh
**Problem**: FPF Live Stats reset to "No stats" when page is refreshed during a run  
**Current State**: Unknown if stats are persisted to DB or only held in memory  
**Expected Behavior**: Refreshing the page should restore current live stats for an in-progress run  
**Investigation**: Check if `fpf_stats` are stored in DB during run, or only at completion

---

### 4. Evaluations Counter Shows 0/0
**Problem**: The "Evaluations" info box always displays "0 / 0"  
**Expected Behavior**: 
- First number: Completed evaluations (live updated)
- Second number: Expected total evaluations (calculated from docs × models × eval types)
**Investigation**: Find where evaluation counts are calculated and passed to UI

---

### 5. Remove Decimal Seconds from All Time Displays
**Problem**: Some time displays may show fractional seconds (e.g., "12.345s")  
**Expected Behavior**: All times should display as whole seconds only (e.g., "12s")  
**Investigation**: Search for time formatting functions and ensure they truncate/round

---

### 6. Evaluation Details Box - White on White Text
**Problem**: In "Timeline & Details" tab, the evaluation details section has white text on white background  
**Expected Behavior**: Text should be black (or dark) for readability  
**Investigation**: Check CSS classes for evaluation detail cards in Timeline tab

---

### 7. Build Preset Page Should Load Default Preset
**Problem**: Build Preset page starts empty  
**Expected Behavior**: Page should load with the "Default Preset" already populated  
**Investigation**: Check BuildPreset component's useEffect for initial data loading

---

### 8. Verify Live Stats Accuracy (Failed/Retry Counts)
**Problem**: Unknown if live stats correctly reflect failed calls and retries  
**Expected Behavior**: Stats should match what's logged in FPF execution logs  
**Investigation**: 
1. Run an execution that has failures/retries
2. Compare FPF log entries to displayed live stats
3. Trace `record_failure()` and `record_retry()` calls through the callback chain

---

### 9. Evaluation Timeout / Slow Evaluations
**Problem**: Evaluations taking too long (unclear if timeout issue or API latency)  
**Expected Behavior**: Reasonable timeouts with clear failure handling  

---

### 12. 🔴 FPF HTTP Retry Loop Has No Total Deadline (CRITICAL BUG)

**Evidence from run cfae3f9d-0ac3-40a1-9cde-dbddf9b989bf:**

Task `d7bfbff9` (gpt-5-mini) timeline:
| Time | Event |
|------|-------|
| 21:48:29 | `[FPF RUN_START] id=d7bfbff9 attempt=1/1` |
| 21:58:30 | `Transient error on attempt 1/3` - First HTTP timeout (600s) |
| 22:08:30 | `Transient error on attempt 2/3` - Second HTTP timeout (600s) |
| 22:18:31 | `FPF run failed: The read operation timed out` - Third timeout (600s) |

**Total: 1801 seconds (30 minutes) for ONE API call**

**Root Cause**: Two separate retry mechanisms:
1. **FPF run-level**: `attempt=1/1` (configured correctly for 1 attempt)
2. **HTTP layer**: `max_retries=3` in `_http_post_json()` ([file_handler.py#L119](../FilePromptForge/file_handler.py#L119))

**The Bug**: HTTP retry loop has NO total deadline. Each retry restarts the 600s timer:
- 600s timeout × 3 retries = **1,800 seconds worst case** per single API call
- This happens INSIDE the FPF run - completely invisible to ACM

**Fix Required in FPF**:
```python
# _http_post_json should accept a deadline parameter
def _http_post_json(url, payload, headers, timeout=600, max_retries=3, deadline=None):
    for attempt in range(1, max_retries + 1):
        if deadline and time.time() > deadline:
            raise RuntimeError("Total execution deadline exceeded")
        # ... existing retry logic
```
- 3 retries × ~400-600s each ≈ 1200-1800s total

**ACM's 86400s (24-hour) subprocess timeout** ([adapter.py#L146](app/adapters/fpf/adapter.py#L146)):
- This is intentional "safety ceiling" - ACM lets FPF manage its own timeouts
- FPF is responsible for exiting in reasonable time

**Possible Enhancement**: Add a "total execution deadline" to FPF config so all API calls must complete by time X

---

### 13. 🔴 Retries NOT Reflected in Live Stats (CRITICAL)
**Problem**: FPF retries are happening but Live Stats shows `retries: 0`  
**Evidence from run cfae3f9d-0ac3-40a1-9cde-dbddf9b989bf**:
```
2025-12-19 21:58:30 WARNING fpf_openai_main: Transient error on attempt 1/3, retrying in 0.41s
2025-12-19 21:58:51 WARNING fpf_openai_main: Transient error on attempt 1/3, retrying in 0.11s
2025-12-19 22:08:30 WARNING fpf_openai_main: Transient error on attempt 2/3, retrying in 0.52s
2025-12-19 22:08:51 WARNING fpf_openai_main: Transient error on attempt 2/3, retrying in 0.73s
```
But the stats broadcast at that time showed:
```python
{'retries': 0, 'failed_calls': 0, ...}  # Wrong! Should show retries
```
**Root Cause**: The retry logic is inside FPF subprocess (fpf_openai_main.py), not in ACM's Judge/FpfStatsTracker. ACM never calls `record_retry()` because it doesn't know about FPF's internal retries.
**Expected Behavior**: Live Stats should show accurate retry count as retries happen
**Fix Required**: Either:
1. Parse FPF stderr for retry patterns and update stats, OR
2. Have FPF emit structured retry events that ACM can capture

---

## INVESTIGATION RESULTS: Task #9 - Run cfae3f9d-0ac3-40a1-9cde-dbddf9b989bf

### Summary of Findings

**Run Timing**:
- Started: 2025-12-19 21:48:29
- FPF subprocess was still running after **1050+ seconds** (17+ minutes)
- Heartbeat logs showed continuous incrementing: 630s, 660s, 690s... 990s, 1020s, 1050s

### Root Cause Analysis

**1. The Slow Model: openai:gpt-5-mini**

The `gpt-5-mini` model takes **200-300+ seconds** per API call due to:
- High reasoning effort (`"effort": "high"`)
- Web search tool calls (multiple searches per request)
- Complex evaluation prompts with mandatory web search verification
- 50,000 max_output_tokens setting

**Example successful call times for gpt-5-mini from FPF logs**:
- `elapsed=290.37s` (3627d2a5)
- `elapsed=296.14s` (9a43a92f)
- `elapsed=227.88s` (a8d3be7c)
- `elapsed=235.10s` (80ebcffa)

**2. Timeout Configuration**

From [file_handler.py](../FilePromptForge/file_handler.py#L375-L395):
```
Default timeout: 600 seconds (10 minutes)
openaidp: 7200 seconds (2 hours) for deep research
tavily: 1800 seconds (30 minutes)
```

**The problem**: The default 600-second timeout is barely enough for gpt-5-mini's 200-300s typical response time. If network latency or API throttling occurs, it will timeout.

**3. Actual Timeouts Observed**

From `fpf_run.log`:
```
2025-12-19 21:54:56 ERROR: HTTP request failed: The read operation timed out
2025-12-19 21:58:46 ERROR: HTTP request failed: The read operation timed out  
2025-12-19 21:59:08 ERROR: HTTP request failed: The read operation timed out
```

**4. Why the ACM Heartbeat Showed 1000+ Seconds**

The ACM subprocess manager was waiting on a hung FPF process that had already timed out internally but the subprocess hadn't exited cleanly. The heartbeat just counts wall-clock time since subprocess start, not individual API call time.

### Full API Payload Example (from 20251219T215337-3627d2a5.json)

```json
{
  "run_id": "3627d2a5",
  "started_at": "2025-12-19T21:48:47",
  "finished_at": "2025-12-19T21:53:37",  // 290 seconds!
  "model": "gpt-5-mini",
  "config": {
    "timeout_seconds": 600,
    "max_completion_tokens": 50000
  },
  "request": {
    "model": "gpt-5-mini",
    "input": [{ "role": "user", "content": "<long evaluation prompt...>" }],
    "max_output_tokens": 50000,
    "tools": [{ "type": "web_search", "search_context_size": "medium" }],
    "tool_choice": "auto",
    "reasoning": { "effort": "high" }
  },
  "response": {
    "status": "completed",
    "model": "gpt-5-mini-2025-08-07",
    // ... web_search_call results, reasoning blocks, etc.
  }
}
```

### Recommendations

1. **Increase timeout for openai provider**: Set `providers.openai.timeout_seconds: 900` (15 minutes) to handle slow gpt-5-mini calls
2. **Consider using faster models for evaluation**: `gemini-2.5-flash` completes in 15-20 seconds
3. **Reduce reasoning effort**: Change from `"high"` to `"medium"` to speed up reasoning models
4. **Add retry on timeout**: Currently no retry on timeout errors (only on rate limits)
5. **Show timeout progress in UI**: Let users know when an API call is taking unusually long

### Comparison: Google vs OpenAI Response Times

| Model | Typical Time | Notes |
|-------|--------------|-------|
| google:gemini-2.5-flash | 15-25s | Fast, includes web search |
| google:gemini-2.5-pro | 40-60s | Slower but more capable |
| openai:gpt-5-mini | 200-300s | Very slow due to reasoning + web search |

---

### 10. Remove FPF Output Tab
**Problem**: There is an "FPF Output" tab on the Execute page that should not exist  
**Expected Behavior**: Remove this tab entirely from the UI  
**Investigation**: Find the tab component and remove it from the render

---

### 11. Page/Console Jerks on Log Write
**Problem**: Both the main page and the console log area jump/jerk when new log entries are written  
**Expected Behavior**: 
- Page should remain stable when logs update
- Console should be independently scrollable
- User's scroll position should be preserved unless they're at the bottom (auto-scroll)
**Investigation**: Check scroll behavior in console component - likely needs `overflow: auto` with stable height and conditional auto-scroll

---

## Priority Order

| Priority | Task | Complexity |
|----------|------|------------|
| HIGH | #3 Live Stats Persist | Medium - may need DB storage |
| HIGH | #4 Evaluations Counter | Low - wiring issue |
| HIGH | #2 Stream Eval Scores | Medium - WebSocket events |
| MEDIUM | #1 Duration Display | Low - formatting |
| MEDIUM | #6 White on White Text | Low - CSS fix |
| MEDIUM | #5 Decimal Seconds | Low - formatting |
| MEDIUM | #11 Page/Console Jerking | Medium - scroll logic |
| LOW | #7 Default Preset | Low - initial state |
| LOW | #10 Remove FPF Output Tab | Low - delete code |
| INVESTIGATE | #8 Stats Accuracy | Analysis first |
| INVESTIGATE | #9 Slow Evaluations | Analysis first |

---

## Files to Investigate

| Component | File Path |
|-----------|-----------|
| Execute page UI | `ui/src/pages/Execute.tsx` |
| Run socket hook | `ui/src/hooks/useRunSocket.ts` |
| FPF Stats tracker | `app/evaluation/__init__.py` |
| Judge (evals) | `app/evaluation/judge.py` |
| Run executor | `app/services/run_executor.py` |
| WebSocket handler | `app/api/websockets.py` |
| Run API endpoints | `app/api/runs.py` |
| Timeline component | `ui/src/components/EvaluationTimeline.tsx` (or similar) |
| Build Preset page | `ui/src/pages/BuildPreset.tsx` |

---

*This document tracks UI/UX issues discovered on the Execute page. Each item needs investigation and implementation.*
