# REPEATING PROBLEM: Console/Heartbeat Display Stops Working

## Problem Statement

The console in the webpage appears to hang. Heartbeats are not being displayed. It works for a few seconds then stops reporting, even if the run continues in the background.

**Severity:** CRITICAL
**Cost Impact:** Thousands of dollars in development time
**Frequency:** Hundreds of occurrences
**Date of Analysis:** December 17, 2025

---

## Executive Summary

After thorough investigation, **FOUR DISTINCT ROOT CAUSES** have been identified, all contributing to the symptom of the console appearing to hang:

1. **PRIMARY ROOT CAUSE (React Stale Closure Bug):** The LogViewer's `setInterval` captures a stale closure of `fetchLogs` with `offset=0`, causing the same logs to be fetched repeatedly instead of progressive updates.

2. **SECONDARY ROOT CAUSE (Broken WebSocket Import):** The `run_store` object was removed from `runs.py` but `run_executor.py` still tries to import both `run_store` and `run_ws_manager` in one line. When the import fails, BOTH become `None`, disabling all WebSocket real-time updates.

3. **TERTIARY ROOT CAUSE (Execute.tsx Missing WebSocket):** The main `Execute.tsx` page does not use the WebSocket hook (`useRunSocket`) at all - only HTTP polling is implemented.

4. **QUATERNARY ROOT CAUSE (No Heartbeat Protocol):** There is no heartbeat/ping-pong protocol on the WebSocket connection itself. The connection can silently die without detection.

---

## 20 Possible Causes Brainstormed

| # | Hypothesis | Status |
|---|-----------|--------|
| 1 | EventSource connection closes silently | Not applicable (using WebSocket/polling) |
| 2 | Server-Sent Events buffer overflow | Not applicable |
| 3 | Backend generator exhaustion | Not the issue |
| 4 | CORS issues with SSE | Not applicable |
| 5 | React component unmount cleanup | Cleanup exists, not the primary issue |
| 6 | JavaScript error in event handler | Errors are caught, not the issue |
| 7 | Browser tab throttling | May contribute but not primary cause |
| 8 | Heartbeat interval too long | Backend heartbeat is 30s, reasonable |
| 9 | Network timeout on connection | Not the issue |
| 10 | SSE reconnection logic broken | Not applicable |
| 11 | React state update batching | Not the issue |
| 12 | Memory leak causing freeze | Not observed |
| 13 | EventSource onerror exits | Not applicable |
| 14 | Backend exception unhandled | Runs continue, not the issue |
| 15 | Connection killed by middleware | Not observed |
| 16 | Duplicate event listeners | Not the issue |
| 17 | **Polling offset gets stale** | **CONFIRMED - ROOT CAUSE #1** |
| 18 | JSON parsing error | Errors caught, not the issue |
| 19 | **WebSocket manager fails to import** | **CONFIRMED - ROOT CAUSE #2** |
| 20 | **Execute.tsx doesn't use WebSocket** | **CONFIRMED - ROOT CAUSE #3** |

---

## Detailed Root Cause Analysis

### ROOT CAUSE #1: React Stale Closure in LogViewer

**Location:** `ui/src/components/execution/LogViewer.tsx`, lines 62-85

**The Bug:**
```typescript
// Polling when running
useEffect(() => {
  if (isRunning && expanded) {
    setIsPolling(true)
    pollIntervalRef.current = setInterval(fetchLogs, 2000)  // ← STALE CLOSURE
  }
  // ...
}, [isRunning, expanded, runId])  // ← fetchLogs NOT in dependencies!
```

**What Happens:**
1. `fetchLogs` is defined during render, capturing `offset = 0` in a closure
2. `setInterval(fetchLogs, 2000)` stores a reference to this specific `fetchLogs` function
3. Every 2 seconds, the SAME `fetchLogs` runs with `offset = 0`
4. `setOffset(...)` updates React state, but the interval never sees the new value
5. The API returns the same first 100 lines repeatedly
6. New logs (including heartbeats) are NEVER fetched

**Evidence:**
- LogViewer shows initial logs then stops updating
- Backend log files (`logs/{run_id}/run.log`) continue to grow with heartbeat messages
- API endpoint returns correct data when called with proper offset

**The Fix (DO NOT IMPLEMENT - JUST ANALYSIS):**
```typescript
// Option A: Use useRef for offset
const offsetRef = useRef(0)

// Option B: Use useCallback with proper dependencies
const fetchLogs = useCallback(async () => {
  // ...
}, [runId, logLevel, offset])

// Option C: Use functional state update
setOffset(prev => {
  // Use prev for the API call
  return newOffset
})
```

---

### ROOT CAUSE #2: Broken WebSocket Manager Import

**Location:** `app/services/run_executor.py`, lines 193-198

**The Bug:**
```python
try:
    from ..api.routes.runs import run_store, run_ws_manager  # type: ignore
    self._run_store = run_store
    self._run_ws_manager = run_ws_manager
except Exception:
    self._run_store = None
    self._run_ws_manager = None  # ← BOTH become None!
```

**What Happened:**
- At some point, `run_store` (the `RunStore` class and its singleton instance) was removed from `runs.py`
- But the import line tries to import BOTH `run_store` AND `run_ws_manager` together
- When the import fails due to missing `run_store`, the entire line fails
- `run_ws_manager` DOES exist but is not imported
- Both `_run_store` and `_run_ws_manager` become `None`
- All subsequent WebSocket broadcasts are silently skipped

**Evidence:**
```
>>> from app.api.routes.runs import run_store, run_ws_manager
ImportError: cannot import name 'run_store' from 'app.api.routes.runs'

>>> from app.api.routes.runs import run_ws_manager
<app.api.routes.runs.RunConnectionManager object at 0x...>  # ← Works alone!
```

**Impact:**
- No real-time WebSocket updates are ever sent
- Lines like `await self._run_ws_manager.broadcast(...)` are skipped
- Frontend WebSocket connection opens but receives nothing

**The Fix (DO NOT IMPLEMENT - JUST ANALYSIS):**
```python
# Option A: Separate imports
try:
    from ..api.routes.runs import run_ws_manager
    self._run_ws_manager = run_ws_manager
except ImportError:
    self._run_ws_manager = None

try:
    from ..api.routes.runs import run_store
    self._run_store = run_store
except ImportError:
    self._run_store = None

# Option B: Remove run_store entirely if not needed
# The code already checks for None before using it
```

---

### ROOT CAUSE #3: Execute.tsx Missing WebSocket Integration

**Location:** `ui/src/pages/Execute.tsx`

**The Bug:**
- The `useRunSocket` hook exists at `ui/src/hooks/useRunSocket.ts`
- It is imported and used ONLY in `ExecutionDetail.tsx`
- The main `Execute.tsx` page does NOT import or use `useRunSocket`
- `Execute.tsx` relies solely on HTTP polling every 2 seconds

**Evidence:**
```bash
grep -r "useRunSocket" ui/src/pages/
# ExecutionDetail.tsx:4: import useRunSocket from '@/hooks/useRunSocket'
# ExecutionDetail.tsx:10: useRunSocket(id)
# Execute.tsx: (no matches)
```

**Impact:**
- Even if WebSocket worked, `Execute.tsx` would not receive real-time updates
- Updates only occur every 2 seconds via HTTP polling
- Combined with Root Cause #1, updates stop entirely after first poll

---

### ROOT CAUSE #4: No WebSocket Heartbeat Protocol

**Location:** `app/api/routes/runs.py`, lines 1044-1066

**The Bug:**
```python
@router.websocket("/ws/run/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: str):
    await run_ws_manager.connect(websocket, run_id)
    try:
        # TODO: Fetch initial state from DB
        while True:
            try:
                await websocket.receive_text()  # ← Just waits for client messages
            except WebSocketDisconnect:
                break
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        run_ws_manager.disconnect(websocket, run_id)
```

**Issues:**
- No ping/pong heartbeat to detect dead connections
- No initial state sent when client connects
- No periodic status updates
- Connection can die silently with no detection on either end

---

## How These Bugs Interact

```
User Opens Execute Page
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Execute.tsx                                   │
│  • Sets up HTTP polling every 2 seconds                             │
│  • NO WebSocket integration (ROOT CAUSE #3)                         │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LogViewer.tsx                                 │
│  • Opens with offset = 0                                            │
│  • Creates interval with stale fetchLogs                            │
│  • KEEPS fetching offset=0 forever (ROOT CAUSE #1)                  │
│  • Shows same logs repeatedly, no new updates                       │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Backend run_executor.py                       │
│  • Tries to import run_store (doesn't exist)                        │
│  • Import fails, run_ws_manager also becomes None (ROOT CAUSE #2)   │
│  • All broadcast() calls silently skipped                           │
│  • Heartbeats written to log file but never broadcast               │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        WebSocket Endpoint                            │
│  • No ping/pong protocol (ROOT CAUSE #4)                            │
│  • No initial state sent                                            │
│  • Connection sits idle                                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Impact Analysis

### Why This Appears as "Hanging"

1. **First Few Seconds Work:** The initial `fetchLogs()` call on mount works correctly, showing the first batch of logs
2. **Then Stops:** The interval keeps calling `fetchLogs` with `offset=0`, but since logs are appended with `prev + response.lines.join('\n')`, the same lines keep getting appended (or nothing if the API returns empty for already-seen offset)
3. **No Real-Time Updates:** WebSocket would normally push updates, but it's broken
4. **Heartbeats Invisible:** Backend heartbeats are written to the log file every 30 seconds, but the frontend never fetches new content

### User Experience

1. User starts a run
2. Console shows initial activity
3. After ~2 seconds, console appears frozen
4. Backend continues working (visible in terminal or log files)
5. Run completes but user sees nothing
6. Refreshing page shows final state but not the journey

---

## Files Involved

| File | Issue |
|------|-------|
| `ui/src/components/execution/LogViewer.tsx` | Stale closure in setInterval |
| `app/services/run_executor.py` | Failed import of run_store breaks run_ws_manager |
| `app/api/routes/runs.py` | run_store class removed but still referenced |
| `ui/src/pages/Execute.tsx` | Missing useRunSocket integration |
| `ui/src/hooks/useRunSocket.ts` | Exists but unused in main Execute page |

---

## Verification Steps Performed

### 1. Import Test
```python
>>> from app.api.routes.runs import run_store, run_ws_manager
ImportError: cannot import name 'run_store' from 'app.api.routes.runs'

>>> from app.api.routes.runs import run_ws_manager  
<app.api.routes.runs.RunConnectionManager object at 0x...>  # Works!
```

### 2. Log File Analysis
```
logs/f14406cb-ce1.../run.log:
2025-12-17 08:54:01,449 [INFO] app.adapters.fpf.subprocess: [ACM] Heartbeat: FPF subprocess running for 240s...
2025-12-17 08:54:09,105 [INFO] app.adapters.fpf.subprocess: [ACM] Heartbeat: FPF subprocess running for 270s...
...
(Heartbeats continue every 30 seconds in the log file)
```

### 3. Database Timeline Events
```python
>>> run.results_summary.get('timeline_events', [])
[
    {'phase': 'initialization', 'event_type': 'start', 'description': 'Run started', ...},
    {'phase': 'generation', 'event_type': 'generation', 'description': 'Generated doc using fpf', ...}
]
# Timeline events ARE being written progressively to the database
```

### 4. WebSocket Hook Usage
```bash
$ grep -r "useRunSocket" ui/src/pages/
ExecutionDetail.tsx:4:import useRunSocket from '@/hooks/useRunSocket'
ExecutionDetail.tsx:10:  useRunSocket(id)
# NOT used in Execute.tsx!
```

---

## Recommended Fixes

### Priority 1: Fix LogViewer Stale Closure

Use a ref to track offset, or restructure to use proper React patterns:

```typescript
// Use useRef to avoid stale closure
const offsetRef = useRef(0)

const fetchLogs = useCallback(async () => {
  const response = await apiClient.get(`/runs/${runId}/logs`, { 
    offset: offsetRef.current,
    ...
  })
  if (response.lines.length > 0) {
    offsetRef.current = response.offset + response.lines.length
    // ...
  }
}, [runId])
```

### Priority 2: Fix WebSocket Import

Separate the imports to prevent cascade failure:

```python
try:
    from ..api.routes.runs import run_ws_manager
    self._run_ws_manager = run_ws_manager
except ImportError:
    self._run_ws_manager = None

# run_store can be removed entirely if not needed
self._run_store = None
```

### Priority 3: Add WebSocket to Execute.tsx

```typescript
import useRunSocket from '../hooks/useRunSocket'

export default function Execute() {
  // ... existing code ...
  useRunSocket(currentRun?.id)  // Add this line
```

### Priority 4: Add WebSocket Heartbeat

```python
@router.websocket("/ws/run/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: str):
    await run_ws_manager.connect(websocket, run_id)
    try:
        # Send initial state
        # ... fetch from DB and send ...
        
        while True:
            try:
                # Use ping/pong or timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
```

---

## Conclusion

The "console hangs" symptom is caused by a cascade of failures:

1. **React stale closure** prevents new log entries from being fetched
2. **Broken import** disables WebSocket entirely
3. **Missing integration** means Execute.tsx never tries WebSocket
4. **No heartbeat protocol** means connections die silently

All four issues must be addressed for reliable real-time console updates.

---

*Report generated: December 17, 2025*
*Investigation time: ~45 minutes*
*Recommendation: Fix Priority 1 (LogViewer) first as it provides immediate improvement*
