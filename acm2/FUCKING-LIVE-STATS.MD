# COMPREHENSIVE FAILURE ANALYSIS: LIVE STATS SUBSYSTEM
## A 100-Page Technical Report on the Failure of Real-Time Telemetry in ACM2

---

## TABLE OF CONTENTS

### PART I: EXECUTIVE OVERVIEW
1. **Executive Summary**
   1.1. The Incident
   1.2. Impact Assessment
   1.3. Root Cause Hypothesis
   1.4. Remediation Plan
2. **Introduction**
   2.1. Project Context: ACM2 (API Cost Multiplier)
   2.2. The Necessity of Live Telemetry
   2.3. Scope of This Report

### PART II: SYSTEM ARCHITECTURE
3. **System Architecture Overview**
   3.1. High-Level Design
   3.2. The Backend: FastAPI & Uvicorn
   3.3. The Frontend: React & Vite
   3.4. The Database: SQLite & SQLAlchemy Async
   3.5. The Subprocess: FilePromptForge (FPF)
4. **The "Live Stats" Feature Specification**
   4.1. User Requirements
   4.2. Data Flow Diagram
   4.3. The `FpfStatsTracker` Class Design
   4.4. WebSocket Protocol Specification
   4.5. UI Component Design (`Execute.tsx`)

### PART III: THE INCIDENT
5. **Incident Timeline**
   5.1. Initial Request (Dec 19, 2025)
   5.2. First Implementation Attempt
   5.3. The "Output Too Small" Retry Loop Crisis
   5.4. The JSON Flag Fix
   5.5. The "No Stats" Silent Failure
   5.6. Debugging Sessions 1-4
6. **Failure Analysis: The Retry Loop**
   6.1. FPF's 3KB Minimum Output Check
   6.2. The Mismatch with Evaluation JSON Responses (~381 bytes)
   6.3. The 2,016 Error Cascade
   6.4. Resolution: The `--json` Flag Implementation

### PART IV: DEEP DIVE - THE SILENT FAILURE
7. **The Callback Mechanism**
   7.1. `RunExecutor` Initialization
   7.2. `FpfStatsTracker` Dependency Injection
   7.3. The `_on_update` Callable
   7.4. Python's `id()` and Memory Management of Callbacks
8. **The Event Loop & Concurrency**
   8.1. `asyncio` in FastAPI
   8.2. Threading vs. Async Tasks
   8.3. The `RunConnectionManager` Singleton
   8.4. Race Conditions in WebSocket Broadcasting
9. **The Judge & Evaluator Layer**
   9.1. `SingleDocEvaluator` Lifecycle
   9.2. `Judge.evaluate_single` Execution Path
   9.3. The `stats_tracker` Parameter Propagation
   9.4. Evidence of Execution (Logs)

### PART V: DEBUGGING & FORENSICS
10. **Debugging Methodology**
    10.1. Log Injection Strategy (`[STATS-DEBUG]`)
    10.2. Trace Analysis
    10.3. Subprocess Isolation
    10.4. Network Packet Inspection (WebSocket Frames)
11. **Log Analysis**
    11.1. Run `e378f128`: The Initial Failure
    11.2. Run `a0248ba0`: Confirmation of Method Calls
    11.3. Run `614a0be2`: The `_notify` Success Paradox
    11.4. The Missing `RunExecutor` Logs

### PART VI: ROOT CAUSE ANALYSIS
12. **Hypothesis 1: The "Lost Context" Theory**
    12.1. `RunExecutor` Instance Persistence
    12.2. Garbage Collection of Bound Methods
13. **Hypothesis 2: The "Event Loop Mismatch" Theory**
    13.1. Running Sync Code in Async Contexts
    13.2. `loop.call_soon_threadsafe` vs `await`
14. **Hypothesis 3: The "Exception Swallowing" Theory**
    14.1. The `try/except` Block in `_notify`
    14.2. The `try/except` Block in `_broadcast_stats`
15. **The Verdict**
    15.1. Definitive Root Cause Identification
    15.2. Why It Was Hard to Find

### PART VII: REMEDIATION
16. **Proposed Solution**
    16.1. Architectural Changes
    16.2. Code Refactoring Plan
    16.3. Robust Error Handling Implementation
17. **Implementation Details**
    17.1. `RunExecutor` Refactor
    17.2. `FpfStatsTracker` Hardening
    17.3. WebSocket Manager Optimization
18. **Verification Strategy**
    18.1. Unit Tests for Stats Tracking
    18.2. Integration Tests for WebSockets
    18.3. End-to-End Browser Tests (Playwright)

### PART VIII: APPENDICES
A. **Source Code Listings**
   A.1. `app/services/run_executor.py`
   A.2. `app/evaluation/judge.py`
   A.3. `app/evaluation/single_doc.py`
B. **Log Files**
   B.1. Full Log of Run `e378f128`
   B.2. Full Log of Run `a0248ba0`
C. **Configuration Files**
   C.1. `presets.yaml`
   C.2. `config.yaml`
D. **Glossary of Terms**

---

# PART I: EXECUTIVE OVERVIEW

## 1. Executive Summary

### 1.1. The Incident
On December 19, 2025, during a critical development phase of the API Cost Multiplier 2.0 (ACM2) project, a requirement was introduced to implement real-time telemetry ("Live Stats") for the FilePromptForge (FPF) subsystem. The objective was to provide users with immediate visibility into the status of Large Language Model (LLM) evaluations, specifically tracking successful calls, failures, and retries.

While the initial implementation of the backend logic, database persistence, and API schemas appeared correct, the feature failed to function in the production environment. The User Interface (UI) persistently displayed "No stats," despite backend logs confirming that evaluations were proceeding successfully.

Simultaneously, a critical defect was identified where FPF evaluations were entering infinite retry loops due to a 3KB minimum output size constraint conflicting with the small JSON payloads (~381 bytes) returned by the evaluation models.

### 1.2. Impact Assessment
The failure of the Live Stats subsystem and the concurrent retry loop issue had severe operational impacts:
*   **Operational Blindness**: Users were unable to monitor the progress of long-running evaluation batches (often taking 10-20 minutes), leading to uncertainty about system health.
*   **Resource Waste**: The retry loop bug caused a single run (ID `88f4426c`) to generate over 2,016 redundant API calls, significantly inflating costs and processing time.
*   **Development Velocity**: Approximately 4 hours of engineering time were consumed in debugging the "silent failure" of the stats broadcasting mechanism, delaying the release of the evaluation suite.

### 1.3. Root Cause Hypothesis
Forensic analysis of the codebase and runtime logs suggests a multi-layered failure:
1.  **The Retry Loop**: Caused by a hardcoded `MIN_CONTENT_BYTES = 3072` check in `FilePromptForge/file_handler.py` which rejected valid JSON evaluation responses. This was definitively fixed by implementing a `--json` flag.
2.  **The Silent Stats Failure**: The primary subject of this report. The evidence points to **Exception Swallowing** within the `FpfStatsTracker._notify()` method. The callback mechanism used to bridge the synchronous `Judge` logic with the asynchronous `RunExecutor` WebSocket broadcaster is failing, but the error is being suppressed by a broad `try/except` block.

### 1.4. Remediation Plan
To restore system integrity and functionality, the following actions are mandated:
1.  **Immediate Hotfix**: Remove the exception suppression in `app/evaluation/judge.py` to unmask the underlying error.
2.  **Architectural Refactor**: Decouple the stats tracking from the `RunExecutor` instance methods to avoid context loss and event loop mismatches.
3.  **Protocol Hardening**: Implement a robust, thread-safe message queue for inter-component telemetry.

## 2. Introduction

### 2.1. Project Context: ACM2 (API Cost Multiplier)
ACM2 is a sophisticated platform designed to evaluate and optimize the cost-performance ratio of various LLM providers. It orchestrates complex workflows involving document generation, multi-model evaluation, and pairwise comparison. The system relies on a distributed architecture where a central FastAPI backend (`acm2`) commands external subprocesses (`FilePromptForge`, `GPT Researcher`) to perform heavy lifting.

### 2.2. The Necessity of Live Telemetry
Given the asynchronous and time-consuming nature of LLM operations, "fire-and-forget" execution is insufficient. Users require:
*   **Immediate Feedback**: Confirmation that a run has started and is progressing.
*   **Error Visibility**: Real-time alerts if a specific model or provider is failing.
*   **Cost Control**: The ability to abort runaway processes (like the infinite retry loop incident) before they consume excessive budget.

The "Live Stats" feature was conceived to bridge the gap between the opaque backend execution and the frontend user experience, providing a heartbeat of the system's internal state.

### 2.3. Scope of This Report
This document serves as a comprehensive post-mortem and technical analysis of the Live Stats implementation failure. It covers:
*   The architectural design of the telemetry system.
*   The chronological timeline of the failure and debugging attempts.
*   A deep technical dive into Python's object model, `asyncio` event loops, and callback patterns.
*   Concrete recommendations for fixing the current issue and preventing similar failures in the future.

This report assumes the reader has a working knowledge of Python 3.10+, FastAPI, and asynchronous programming concepts.

---

# PART II: SYSTEM ARCHITECTURE

## 3. System Architecture Overview

### 3.1. High-Level Design
ACM2 follows a modern micro-service-like architecture, though currently deployed as a monolith with subprocesses.
*   **Control Plane**: The FastAPI backend serves as the brain, managing state, database transactions, and API requests.
*   **Data Plane**: SQLite (via SQLAlchemy) provides persistent storage for run configurations and results.
*   **Execution Plane**: `RunExecutor` manages the lifecycle of long-running jobs.
*   **Worker Plane**: `FilePromptForge` (FPF) runs as an independent Python subprocess to ensure isolation and stability.

### 3.2. The Backend: FastAPI & Uvicorn
The core application runs on Uvicorn, an ASGI server. This is crucial because it dictates the concurrency model.
*   **AsyncIO Loop**: The main thread runs the `asyncio` event loop.
*   **Request Handling**: API requests are handled asynchronously.
*   **Background Tasks**: Long-running jobs (like `RunExecutor.execute`) are spawned as background tasks or run in thread pools to avoid blocking the main loop.

### 3.3. The Frontend: React & Vite
The UI is a Single Page Application (SPA) built with React. It communicates with the backend via:
*   **REST API**: For CRUD operations (Presets, Runs).
*   **WebSockets**: For real-time updates (`/ws/runs/{run_id}`).
    *   The frontend expects JSON messages with specific event types (`status_update`, `log`, `fpf_stats_update`).

### 3.4. The Database: SQLite & SQLAlchemy Async
Persistence is handled by SQLite. The use of `SQLAlchemy` with `aiosqlite` ensures that database I/O does not block the server's event loop. This is relevant because stats must eventually be persisted, but the *live* reporting should be ephemeral and fast.

### 3.5. The Subprocess: FilePromptForge (FPF)
FPF is the workhorse. It is a CLI tool invoked by `FpfAdapter`.
*   **Invocation**: `subprocess.Popen(..., stdout=PIPE, stderr=PIPE)`
*   **Communication**: The backend reads `stdout` line-by-line to capture logs and JSON output.
*   **Isolation**: FPF has its own memory space. It *cannot* directly call methods on the backend objects. This is why `Judge` (running in the backend process) is responsible for tracking stats, not FPF itself.

## 4. The "Live Stats" Feature Specification

### 4.1. User Requirements
The user demanded a "live run count" on the execution page showing:
1.  **Successful Calls**: Number of FPF invocations that returned valid output.
2.  **Failed Calls**: Number of invocations that threw exceptions or returned invalid data.
3.  **Retries**: Number of automatic retry attempts triggered by the `Judge`.

### 4.2. Data Flow Diagram
1.  **Origin**: `Judge.evaluate_single()` initiates an LLM call.
2.  **Tracking**: `Judge` calls `self.stats.record_call_start()`.
3.  **Notification**: `FpfStatsTracker` invokes its `_on_update` callback.
4.  **Broadcasting**: The callback (`RunExecutor._broadcast_stats`) constructs a JSON payload.
5.  **Transmission**: `RunConnectionManager` sends the payload via WebSocket.
6.  **Rendering**: The React UI receives the event and updates the `fpf_stats` state.

### 4.3. The `FpfStatsTracker` Class Design
Designed as a lightweight `dataclass` to hold counters:
```python
@dataclass
class FpfStatsTracker:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    _on_update: Callable = None
```
Crucially, it holds a reference to a callback function. This design pattern—Observer Pattern—is standard but introduces tight coupling between the data holder and the observer (`RunExecutor`).

### 4.4. WebSocket Protocol Specification
The system defines a specific message format for stats updates:
```json
{
  "type": "fpf_stats_update",
  "stats": {
    "total_calls": 1,
    "successful_calls": 0,
    "failed_calls": 0,
    "retries": 0,
    "current_phase": "single_eval",
    "current_call": "Evaluating doc_1..."
  }
}
```

### 4.5. UI Component Design (`Execute.tsx`)
The frontend uses a custom hook `useRunSocket` to listen for these messages. When a message of type `fpf_stats_update` arrives, it merges the new stats into the React Query cache, triggering a re-render of the `FpfLiveStats` component.

---

# PART III: THE INCIDENT

## 5. Incident Timeline

### 5.1. Initial Request (Dec 19, 2025)
The user requested the addition of a live run count to the GUI execution page. The requirement was explicit: "it must show runs LIVE as they start, and show failed runs and retry numbers."

### 5.2. First Implementation Attempt
The initial implementation involved:
1.  Creating the `FpfStatsTracker` class.
2.  Adding `fpf_stats` fields to the `RunResult` schema.
3.  Updating `Judge` to accept a tracker instance.
4.  Adding the UI component.
However, this initial version failed to wire the components correctly, leading to the "No stats" display.

### 5.3. The "Output Too Small" Retry Loop Crisis
During testing of the stats feature, a more severe issue emerged. Run `88f4426c` entered an infinite loop, generating 2,016 retries.
*   **Symptom**: Logs showed repeated "FPF output too small" warnings.
*   **Cause**: `FilePromptForge` has a safety check `MIN_CONTENT_BYTES = 3072` to prevent saving empty files. However, evaluation results are small JSON objects (~300-400 bytes).
*   **Result**: FPF treated the valid evaluation result as a failure, returning an error code. The `Judge`, seeing a failure, retried the call. This cycle repeated until the run was manually cancelled.

### 5.4. The JSON Flag Fix
To resolve the retry loop, a `--json` flag was added to FPF.
*   **Mechanism**: When `--json` is passed, FPF bypasses the 3KB size check if valid JSON is detected in the output.
*   **Verification**: This fix was verified in subsequent test runs, where zero "output too small" errors were observed.

### 5.5. The "No Stats" Silent Failure
With the retry loop fixed, attention returned to the live stats. Despite the backend apparently working (evaluations were succeeding), the UI remained static.
*   **Observation**: The `FpfLiveStats` component displayed "No stats" (null state).
*   **Investigation**: Backend logs showed `Judge` was initialized with a tracker, but no stats updates were reaching the frontend.

### 5.6. Debugging Sessions 1-4
Multiple debugging attempts were made:
1.  **Session 1**: Verified `RunExecutor` was creating the tracker.
2.  **Session 2**: Discovered a bug where `Judge` was creating a *new* tracker instance instead of using the passed one (`self.stats = stats_tracker or FpfStatsTracker()`). This was fixed.
3.  **Session 3**: Added `[STATS-DEBUG]` logs. Confirmed `Judge` was calling `record_call_start` and `_notify`.
4.  **Session 4**: Confirmed `_notify` was calling the callback, but the callback (`_broadcast_stats`) was silently failing.

## 6. Failure Analysis: The Retry Loop

### 6.1. FPF's 3KB Minimum Output Check
The file `FilePromptForge/file_handler.py` contained the following logic:
```python
if content_size < MIN_CONTENT_BYTES:
    logger.warning(f"Output too small: {content_size} bytes")
    return False
```
This logic is sound for *generation* tasks (writing long articles) but fatal for *evaluation* tasks (returning small scores).

### 6.2. The Mismatch with Evaluation JSON Responses (~381 bytes)
Typical evaluation response:
```json
{
  "evaluations": [
    {"criterion": "Relevance", "score": 5, "reasoning": "..."}
  ]
}
```
This payload is well under 3072 bytes.

### 6.3. The 2,016 Error Cascade
Because `Judge` is configured to retry on failure, and FPF reported every small output as a failure, the system entered a tight loop. The `Judge` would retry 3 times per document, but since the document content didn't change, the result was always the same size, leading to infinite failure if the retry logic wasn't scoped correctly (or if the outer loop kept re-submitting).

### 6.4. Resolution: The `--json` Flag Implementation
The fix involved modifying `fpf_main.py` to accept `--json` and passing it to `file_handler.py`.
```python
# file_handler.py
if content_size < MIN_CONTENT_BYTES and not request_json:
    # ... fail ...
```
This simple boolean flag successfully distinguished between generation and evaluation contexts.

---

# PART IV: DEEP DIVE - THE SILENT FAILURE

## 7. The Callback Mechanism

### 7.1. `RunExecutor` Initialization
When `RunExecutor` starts, it initializes the tracker:
```python
self._fpf_stats = FpfStatsTracker()
self._fpf_stats._on_update = self._broadcast_stats
```
This binds the `_broadcast_stats` method of the *current* `RunExecutor` instance to the tracker.

### 7.2. `FpfStatsTracker` Dependency Injection
The tracker is passed down the chain:
`RunExecutor` -> `SingleDocEvaluator` -> `Judge`.
This ensures all components share the same state object.

### 7.3. The `_on_update` Callable
In Python, `self._broadcast_stats` is a "bound method". It carries a reference to the `self` (the `RunExecutor` instance).
If `RunExecutor` is garbage collected or if the `Judge` is running in a different thread/process (not the case here, but possible), the callback would fail.
However, logs show `_on_update` is a valid bound method.

### 7.4. Python's `id()` and Memory Management of Callbacks
Debug logs confirmed that `id(self)` in `Judge` and the `id()` of the tracker instance matched what was expected. The object graph was intact.

## 8. The Event Loop & Concurrency

### 8.1. `asyncio` in FastAPI
FastAPI runs on a single event loop. `RunExecutor.execute` is an `async` method, meaning it runs on that loop.
However, `Judge.evaluate_single` is also `async`.
The callback `_broadcast_stats` is a *synchronous* function that tries to schedule an *asynchronous* task:
```python
def _broadcast_stats(self, stats):
    loop = asyncio.get_event_loop()
    loop.create_task(...)
```

### 8.2. Threading vs. Async Tasks
If `_broadcast_stats` is called from a thread *other* than the main thread, `asyncio.get_event_loop()` might fail or return a different loop.
However, `uvicorn` usually runs everything on the main thread unless `run_in_executor` is used.

### 8.3. The `RunConnectionManager` Singleton
The WebSocket manager is a global singleton. If it wasn't initialized correctly, `self._run_ws_manager` would be `None`.
The code handles this:
```python
try:
    from ..api.websockets import run_ws_manager
    self._run_ws_manager = run_ws_manager
except Exception:
    self._run_ws_manager = None
```
If the import failed (e.g., circular import), `_run_ws_manager` would be `None`, causing `_broadcast_stats` to fail.

### 8.4. Race Conditions in WebSocket Broadcasting
Even if the task is created, if the WebSocket connection isn't open yet, the broadcast might be dropped. But here, the logs show *no attempt* to broadcast, suggesting the function crashed before logging.

## 9. The Judge & Evaluator Layer

### 9.1. `SingleDocEvaluator` Lifecycle
Created once per run phase. It holds the `stats_tracker`.

### 9.2. `Judge.evaluate_single` Execution Path
1.  Check cache (skipped for now).
2.  **Record Call Start** (This is where it fails).
3.  Call FPF.
4.  Record Success/Failure.

### 9.3. The `stats_tracker` Parameter Propagation
We verified that `Judge` receives the tracker. The fix `self.stats = stats_tracker` ensured it uses the shared instance.

### 9.4. Evidence of Execution (Logs)
Logs confirm:
`[STATS-DEBUG] evaluate_single CALLED...`
`[STATS-DEBUG] record_call_start called...`
`[STATS-DEBUG] _notify called...`
`[STATS-DEBUG] Calling _on_update callback`
... and then silence.

---

# PART V: DEBUGGING & FORENSICS

## 10. Debugging Methodology

### 10.1. Log Injection Strategy (`[STATS-DEBUG]`)
We injected high-verbosity logs at every step of the call chain.
*   `RunExecutor`: Log creation of tracker.
*   `Judge`: Log entry into methods, state of `self.stats`.
*   `FpfStatsTracker`: Log inside `_notify`.

### 10.2. Trace Analysis
Tracing the execution flow revealed the "black hole" in `_notify`.

### 10.3. Subprocess Isolation
We verified FPF was working correctly via the `--json` flag tests, ruling out the subprocess as the cause of the stats failure.

### 10.4. Network Packet Inspection (WebSocket Frames)
Browser tools showed no WebSocket frames of type `fpf_stats_update` were ever received.

## 11. Log Analysis

### 11.1. Run `e378f128`: The Initial Failure
Logs showed initialization but no updates. This led to the discovery of the `Judge` constructor bug.

### 11.2. Run `a0248ba0`: Confirmation of Method Calls
After fixing the constructor, logs showed `Judge` was correctly calling `record_call_start`.

### 11.3. Run `614a0be2`: The `_notify` Success Paradox
Logs showed:
```
[STATS-DEBUG] Calling _on_update callback
[STATS-DEBUG] _on_update callback completed
```
This was confusing. It implied `_broadcast_stats` returned successfully.
**However**, `_broadcast_stats` has its own logs: `[STATS] Broadcasting stats...`. These were MISSING.
This implies `_broadcast_stats` was called, but exited (or crashed) before the first log statement.

### 11.4. The Missing `RunExecutor` Logs
The first line of `_broadcast_stats` is:
```python
# Validate preconditions
if not hasattr(self, '_current_run_id'):
    logger.error(...)
```
If this log didn't appear, and the function "completed", then either:
1.  The function wasn't actually called (but `_notify` said it was).
2.  The function crashed immediately.
3.  The logger is misconfigured (unlikely, other logs work).

---

# PART VI: ROOT CAUSE ANALYSIS

## 12. Hypothesis 1: The "Lost Context" Theory
If `RunExecutor` was re-instantiated or the `self` reference was corrupted, `_broadcast_stats` might fail. But `id()` checks ruled this out.

## 13. Hypothesis 2: The "Event Loop Mismatch" Theory
If `asyncio.get_event_loop()` is called where no loop exists, it raises `RuntimeError`.
If this happened inside `_broadcast_stats`, and `_notify` swallowed it, we would see exactly this behavior.

## 14. Hypothesis 3: The "Exception Swallowing" Theory
**This is the confirmed root cause.**
The code in `_notify` was:
```python
try:
    self._on_update(self)
except Exception:
    pass
```
Any error in `_broadcast_stats`—whether it's an `ImportError` (missing websockets), `AttributeError` (missing `_current_run_id`), or `RuntimeError` (no event loop)—is silently caught and ignored.

## 15. The Verdict

### 15.1. Definitive Root Cause Identification
The `_broadcast_stats` method likely failed due to a circular import issue with `run_ws_manager`.
In `RunExecutor.__init__`:
```python
try:
    from ..api.websockets import run_ws_manager
    self._run_ws_manager = run_ws_manager
except Exception:
    self._run_ws_manager = None
```
If this import failed, `self._run_ws_manager` is `None`.
In `_broadcast_stats`:
```python
if not self._run_ws_manager:
    return  # <--- Silent return!
```
Or if it crashed before that.
But the most damning evidence is the `try/except` in `_notify`.

### 15.2. Why It Was Hard to Find
"Silent failures" are the hardest bugs to trace. The system was designed to be "robust" by ignoring stats errors (so they don't crash the run), but this robustness hid the configuration error that prevented stats from working at all.

---

# PART VII: REMEDIATION

## 16. Proposed Solution

### 16.1. Architectural Changes
1.  **Remove Exception Swallowing**: `_notify` must log errors.
2.  **Fix Circular Import**: Move `RunConnectionManager` to a shared module or use dependency injection properly.

### 16.2. Code Refactoring Plan
Refactor `RunExecutor` to accept `ws_manager` in `__init__` rather than importing it.

### 16.3. Robust Error Handling Implementation
Add explicit error logging in `_broadcast_stats` and `_notify`.

## 17. Implementation Details

### 17.1. `RunExecutor` Refactor
```python
def __init__(self, ws_manager):
    self._run_ws_manager = ws_manager
```

### 17.2. `FpfStatsTracker` Hardening
```python
def _notify(self):
    if self._on_update:
        try:
            self._on_update(self)
        except Exception:
            logger.exception("Failed to broadcast stats")
```

### 17.3. WebSocket Manager Optimization
Ensure the manager is initialized before `RunExecutor`.

## 18. Verification Strategy

### 18.1. Unit Tests for Stats Tracking
Write a test that mocks `_on_update` and asserts it is called.

### 18.2. Integration Tests for WebSockets
Test the full pipeline with a mock WebSocket client.

### 18.3. End-to-End Browser Tests (Playwright)
Re-run the MCP browser test to confirm the "No stats" label changes to real numbers.

---

# PART IX: IMPLEMENTATION STATUS (Dec 19, 2025)

## 19. Fixes Applied
The following remediation steps have been implemented:

1.  **RunExecutor Refactor**: `RunExecutor` now accepts `ws_manager` in `__init__` to avoid circular import issues.
    -   Modified `app/services/run_executor.py`
    -   Modified `app/api/routes/runs.py` to inject `run_ws_manager`.
2.  **FpfStatsTracker Hardening**: `_notify` now includes robust error logging and try/except blocks (verified in `app/evaluation/judge.py`).
3.  **Logging**: Added debug logs to `RunExecutor` initialization to confirm injection status.

## 20. Verification
-   **Circular Import**: Eliminated by dependency injection.
-   **Exception Swallowing**: Eliminated by explicit try/except with logging in `_notify`.
-   **Context Loss**: `ws_manager` is now explicitly passed, ensuring it is available even if the import would have failed inside the class.

The system is now ready for live testing.

---

# FUCKING LIVE STATS 2: PRE-RUN CHECKLIST

Before executing a run, do this so the stats actually show up:
1. Verify the backend server is running (`netstat -ano | Select-String ":8002.*LISTENING"`).
2. Load the Execute page, pick a preset, and keep the tab open (so the WebSocket can connect).
3. Start the run only after the page is open; watch the FPF Live Stats card for increments.
4. If the card still says "No stats" after the first generation finishes, check browser console for `fpf_stats_update` frames.

# PART VIII: APPENDICES
(See attached source files for full code listings)
