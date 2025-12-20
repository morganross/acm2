# FUCKING-LIVE-STAT-11: Orphaned Run Analysis

**Date:** December 20, 2025, 01:16 AM  
**Run ID:** `066d07f9-96e5-4f2f-996d-78b66c493072`  
**Status in DB:** `running` (should be `failed`)  
**Actual Status:** ORPHANED (server restarted, background task killed)

---

## 1. Executive Summary

This investigation reveals a **critical orphaned run bug**: when the Uvicorn server restarts, any in-progress runs are abandoned with:
- Status stuck as `running` forever
- No `completed_at` timestamp
- FPF subprocess killed without cleanup
- WebSocket broadcasts showing 0 connections throughout

The run started at **23:50:42**, made progress through 7 successful FPF calls, then hung on the 8th call (`gpt-5-mini`). At **00:10:34**, the server restarted, killing everything—but the database was never updated.

---

## 2. Timeline of Events

| Time | Event | Evidence |
|------|-------|----------|
| 23:50:41 | Run created in DB | `created_at` timestamp |
| 23:50:42 | Run started | `started_at` timestamp |
| 23:50:42 | First FPF calls started | `[FPF ERR] INFO fpf_main: Starting FPF runner` |
| 23:51:04 | gemini-2.5-flash & gemini-2.5-pro completed | Generated files created |
| 23:55:56 | First gpt-5.1 call completed (313s) | `FPF subprocess completed in 313s` implied |
| 00:00:37 | Second phase FPF calls | Heartbeats continue |
| 00:04:12 | **gpt-5-mini call started** | `id=1cad298e kind=rest provider=openai model=gpt-5-mini` |
| 00:04:12 | Last stats broadcast | `total_calls: 7, successful_calls: 7` |
| 00:04:14 → 00:10:14 | Heartbeats continue | 811s → 1172s (6 minutes of heartbeats) |
| 00:10:14 | **Last heartbeat logged** | `Heartbeat: FPF subprocess running for 1172s...` |
| 00:10:34 | **Server restarted** | Uvicorn PID 7028/9360 started |
| NOW | Run still shows `running` | DB query confirms |

---

## 3. Root Cause Analysis

### 3.1 Primary Issue: No Orphan Detection/Recovery

When the server restarts:
1. The background task executing the run is killed
2. The FPF subprocess is killed (SIGTERM)
3. **No cleanup code runs**
4. Database is left in inconsistent state

### 3.2 Contributing Factor: 24-Hour Safety Timeout

```python
# From adapter.py line 146:
returncode, stdout, stderr = await run_fpf_subprocess(
    fpf_cmd,
    self._get_fpf_directory(),
    timeout=86400.0,  # 24hr safety ceiling - FPF controls actual timeout
    ...
)
```

The subprocess timeout is **86400 seconds (24 hours)**, meaning even if FPF hangs, the subprocess won't be killed for a full day. This is documented as "FPF controls actual timeout internally" but:
- If the server restarts, this is irrelevant
- If FPF's internal timeout fails, there's no safety net

### 3.3 Contributing Factor: Zero WebSocket Connections

Throughout this entire run, **ALL** WebSocket broadcasts showed `0 connections`:

```log
2025-12-20 00:04:12,022 [INFO] app.api.websockets: [WS] Broadcasting to run 066d07f9...: 0 connections.
```

This indicates:
1. No UI was actively watching the run
2. Even if UI was open, the connection wasn't established
3. Or the connection was dropped and never reconnected

### 3.4 The Stuck gpt-5-mini Call

The FPF subprocess `1cad298e` started at 00:04:12 for model `gpt-5-mini`:

```log
[FPF RUN_START] id=1cad298e kind=rest provider=openai model=gpt-5-mini
```

It successfully:
- Loaded the provider module (`providers.openai.fpf_openai_main`)
- Started the run

But then **no further output** for 6 minutes until the server restarted. This suggests:
- OpenAI API call hung without response
- Or FPF itself hung waiting

### 3.5 Stale `last_error` Not Cleared

The stats showed a stale `last_error` even after 7 successful calls:

```log
'last_error': 'Retry 2: Found JSON-like content but failed to parse: Expecting property name...'
```

This error is from a **previous retry**, not a current failure. Successful calls should clear `last_error` but don't.

---

## 4. Artifacts Produced

| File | Size | Created |
|------|------|---------|
| `7469e725.225b.fpf.1.openai_gpt-5.1.md` | 48,787 bytes | 00:04:12 |
| `7469e725.6a96.fpf.1.google_gemini-2.5-flash.md` | 9,991 bytes | 23:51:04 |
| `7469e725.b8a0.fpf.1.google_gemini-2.5-pro.md` | 6,700 bytes | 23:51:04 |
| `run.log` | 237,869 bytes | 00:10:14 |

**Missing:**
- `7469e725.????.fpf.1.openai_gpt-5-mini.md` - never created (call interrupted)

---

## 5. Database State

```sql
SELECT id, status, created_at, started_at, completed_at FROM runs WHERE id='066d07f9-96e5-4f2f-996d-78b66c493072';
```

| id | status | created_at | started_at | completed_at |
|----|--------|------------|------------|--------------|
| 066d07f9... | running | 2025-12-20 07:50:41 | 2025-12-20 07:50:42 | NULL |

**Note:** Times are UTC (07:50 = 23:50 local)

---

## 6. Critical Bugs Identified

### BUG 1: No Server Restart Recovery (CRITICAL)

**Problem:** When server restarts, runs in `running` state are orphaned forever.

**Impact:** 
- Users see "running" status indefinitely
- Cannot restart or delete orphaned runs
- Database accumulates zombie runs

**Fix Required:**
```python
# On app startup:
async def startup_event():
    # Find all runs with status='running'
    orphaned_runs = await run_repo.get_runs_by_status('running')
    for run in orphaned_runs:
        # Check if run was actually running (has started_at but no completed_at)
        if run.started_at and not run.completed_at:
            await run_repo.update_run(
                run_id=run.id,
                status='failed',
                error_message='Run orphaned by server restart',
                completed_at=datetime.utcnow()
            )
            logger.warning(f"Marked orphaned run {run.id} as failed")
```

### BUG 2: 24-Hour Timeout is Too Long (HIGH)

**Problem:** Subprocess safety timeout of 24 hours provides no real protection.

**Impact:**
- Hung FPF calls won't be killed for 24 hours
- Resource waste (memory, file handles)
- User must manually intervene

**Fix Required:**
```python
# In adapter.py:
timeout=1800.0,  # 30 minute safety ceiling (still generous for gpt models)
```

### BUG 3: `last_error` Not Cleared on Success (MEDIUM)

**Problem:** Stale error messages persist after successful calls.

**Impact:**
- Confusing UI display
- May appear as if current call failed

**Fix Required:**
```python
# In FpfStatsTracker.record_success():
def record_success(self, ...):
    self._successful_calls += 1
    self._last_error = None  # Clear previous error
    self._notify()
```

### BUG 4: No Process Health Monitoring (MEDIUM)

**Problem:** No heartbeat or health check from subprocess back to ACM.

**Impact:**
- Cannot distinguish between "slow API call" and "completely hung"
- No way to detect if FPF subprocess died unexpectedly

**Fix Required:**
- FPF should emit periodic heartbeats to stdout
- ACM should detect absence of heartbeats and kill subprocess

---

## 7. WebSocket Analysis

Every single broadcast showed **0 connections**:

```
Total broadcasts logged: ~10+
Connections for each: 0
```

This could mean:
1. User never opened the run detail page
2. User opened page but WebSocket failed to connect
3. Connection established but dropped before broadcasts

**Recommendation:** Add WebSocket connection logging:
- Log when connections are established
- Log when connections are dropped
- Log reconnection attempts

---

## 8. Comparison to Previous Reports

| Issue | Status | First Seen |
|-------|--------|------------|
| 3KB minimum output check | FIXED | Report 1 |
| Generation phase not tracked | FIXED | Report 2 |
| .pyc cache stale code | FIXED | Report 2 |
| Judge creating new tracker | FIXED | Report 3 |
| Exception swallowing | FIXED | Report 4 |
| Run ID mismatch | FIXED | Report 5 |
| WebSocket URL mismatch | FIXED | Report 6 |
| WebSocket race condition | MITIGATED | Report 7 |
| Orphaned run on restart | **NEW** | Report 11 |
| 24hr timeout too long | **NEW** | Report 11 |
| `last_error` not cleared | **NEW** | Report 11 |

---

## 9. Immediate Actions Required

### Action 1: Fix This Specific Run (Manual)

```sql
UPDATE runs 
SET status='failed', 
    completed_at='2025-12-20 08:10:34', 
    error_message='Orphaned by server restart at 00:10:34'
WHERE id='066d07f9-96e5-4f2f-996d-78b66c493072';
```

### Action 2: Implement Startup Orphan Recovery

Priority: **CRITICAL**

Add to FastAPI app startup:
- Query for runs with status='running'
- Mark as failed with appropriate message
- Log warning for operator awareness

### Action 3: Reduce Safety Timeout

Priority: **HIGH**

Change from 86400s (24h) to 1800s (30min) or 3600s (1hr).

### Action 4: Clear `last_error` on Success

Priority: **MEDIUM**

Add `self._last_error = None` to `record_success()`.

---

## 10. Questions for Future Investigation

1. **Why did gpt-5-mini hang?**
   - Was it an OpenAI API issue?
   - Was it a rate limit?
   - Was it a network issue?

2. **Why did server restart at 00:10:34?**
   - Manual restart?
   - Crash?
   - Auto-reload due to file change?

3. **Why 0 WebSocket connections throughout?**
   - Was UI open?
   - Is there a connection leak?
   - Is reconnection logic broken?

---

## 11. Conclusion

This run exposed a **fundamental architectural flaw**: ACM2 assumes the server will never restart during a run. In reality:
- Servers crash
- Servers are restarted for updates
- Servers may be killed by OS (OOM, etc.)

The fix is straightforward: on startup, detect and mark orphaned runs. This is standard practice for any system with long-running background tasks.

Additionally:
- 24-hour timeout is absurdly long and should be reduced
- Error state should be cleared when calls succeed
- Process health monitoring would catch hung subprocesses

---

*End of FUCKING-LIVE-STAT-11*
