# LIVE STATS 3: TEST PREDICTIONS

**Date**: December 19, 2025  
**Test Phase**: Post-frontend wiring fix

---

## CHANGES MADE THIS SESSION

### 1. useRunSocket.ts
- Added optional `handlers` parameter with callbacks: `onRunUpdate`, `onTaskUpdate`, `onTasksInit`, `onStatsUpdate`
- When `fpf_stats_update` event arrives via WebSocket, it now:
  1. Updates React Query cache (existing behavior)
  2. Calls `onStatsUpdate?.(msg.stats)` to notify consuming components directly

### 2. Execute.tsx
- Added `handleStatsUpdate` callback that sets `currentRun.fpf_stats` in local state
- Added `handleRunUpdate`, `handleTaskUpdate`, `handleTasksInit` callbacks
- All polling/hydration paths now **preserve existing fpf_stats** if the API response has `fpf_stats: null`
- Set `currentRun` immediately after creating run (before `/start`) so WebSocket can attach early

---

## PREDICTIONS FOR NEXT TEST

### ✅ EXPECTED: Stats Will Update Live
**Confidence: 85%**

The previous failure was caused by:
1. WebSocket events updating React Query cache, but Execute.tsx reading from local `currentRun` state
2. Polling overwriting `fpf_stats` with `null` from API (which doesn't persist live stats)

Both issues are now addressed. The `onStatsUpdate` callback directly updates local state, and polling preserves existing stats.

### ⚠️ POSSIBLE ISSUE: Initial "No stats" Flash
**Confidence: 60%**

The WebSocket won't receive stats until:
1. The run is created
2. The WebSocket connects (async, may take ~100ms)
3. The first generation/evaluation starts

If generation starts before WebSocket connects, the first stat event may be missed. The UI will catch up on the second event.

### ⚠️ POSSIBLE ISSUE: Stale Stats on Page Refresh
**Confidence: 90%**

If the user refreshes the page mid-run:
- API returns `fpf_stats: null` (stats are not persisted to DB during run)
- WebSocket reconnects and will receive future events
- Stats counter will "reset" visually until next WebSocket message arrives

This is a known limitation; stats are ephemeral until run completion.

### ❌ UNLIKELY: Stats Still "No stats" Forever
**Confidence: 15%**

This would indicate one of:
1. `_broadcast_stats` in Python backend is still not firing (unlikely, we saw logs last time)
2. WebSocket connection failing silently
3. Event type mismatch (`fpf_stats_update` vs something else)

---

## TEST PROCEDURE

1. **Verify server is running**:
   ```powershell
   netstat -ano | Select-String ":8002.*LISTENING"
   ```

2. **Open browser to Execute page** (http://localhost:8002/execute)

3. **Open browser DevTools → Network → WS tab** to watch WebSocket frames

4. **Select a preset and click Start Execution**

5. **Watch the FPF Live Stats card** - should change from "No stats" to actual numbers within 30 seconds

6. **Verify WebSocket frames** - look for messages containing `"event": "fpf_stats_update"`

---

## SUCCESS CRITERIA

| Metric | Pass | Fail |
|--------|------|------|
| Stats card shows numbers during generation | ✅ | ❌ |
| Stats update multiple times during run | ✅ | ❌ |
| Counts increment (not reset to 0) | ✅ | ❌ |
| "Current call" info appears when running | ✅ (bonus) | — |

---

## IF IT FAILS AGAIN

Check in this order:

1. **Browser console errors** - Any JS exceptions?
2. **WebSocket frames** - Are `fpf_stats_update` messages arriving?
3. **Backend logs** - Is `[STATS] _broadcast_stats ENTERED!` appearing?
4. **React state** - Add `console.log` in `handleStatsUpdate` to verify it's called

---

## TEST RESULTS (December 19, 2025 @ 9:24 PM)

### ❌ FAILED: Stats Still Show "No stats"

**Prediction accuracy: 15% scenario occurred**

### Findings

1. **Backend IS broadcasting stats** - Logs confirm:
   ```
   [STATS] _broadcast_stats ENTERED! run_id=9c756650-382e-4871-947e-04bea2d9cab1
   [STATS] Broadcasting stats for run 9c756650-382e-4871-947e-04bea2d9cab1:
   {'total_calls': 4, 'successful_calls': 4, 'failed_calls': 0, 'retries': 0, ...}
   [STATS] WebSocket broadcast task created for run 9c756650-382e-4871-947e-04bea2d9cab1
   ```

2. **UI still shows "No stats"** after 20+ seconds of execution

### 🔴 ROOT CAUSE IDENTIFIED: RUN ID MISMATCH

**Critical observation from logs:**
- The **current UI run** is: `ad4ed73a-8acc-4bff-8476-db8772196627`
- The **broadcast target run** is: `9c756650-382e-4871-947e-04bea2d9cab1`

**These are DIFFERENT run IDs!**

The `RunExecutor` is using `_current_run_id` from a **stale/previous run**, not the run that the UI just started. This means:
1. WebSocket is connected to `ad4ed73a-...`
2. Backend is broadcasting to `9c756650-...`
3. Messages never reach the correct WebSocket room

### Why This Happened

The `RunExecutor` instance is being reused across runs, but `_current_run_id` is set at `execute()` start. If:
1. An old run started first (9c756650)
2. A new run was created from UI (ad4ed73a)
3. The old executor's stats callback is still firing

...then broadcasts go to the wrong room.

### Fix Required

In `run_executor.py`, ensure `_current_run_id` is set correctly at the START of each `execute()` call, and verify the callback closure captures the correct run ID.

---

*End of test. Root cause: run ID mismatch between executor and UI.*
