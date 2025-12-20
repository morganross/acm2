# Live Stats Debug Report

## Issue Description
The "Live Stats" feature in the UI is not updating during execution, displaying "No stats" even though evaluations are running successfully.

## Verified Working Components
1.  **JSON Flag Fix**: The `--json` flag is correctly passed to FPF, preventing the "output too small" retry loops.
2.  **Stats Initialization**: `RunExecutor` correctly initializes `FpfStatsTracker` and assigns the `_broadcast_stats` callback.
3.  **Dependency Injection**: The `FpfStatsTracker` instance is correctly passed down from `RunExecutor` -> `SingleDocEvaluator` -> `Judge`.
4.  **Method Invocation**: Debug logs confirm that `Judge.evaluate_single` calls `stats.record_call_start`.
5.  **Tracker Notification**: `FpfStatsTracker._notify` is called and detects a valid `_on_update` callback (`bool(_on_update)` is True).

## The Failure Point
Despite `_notify` attempting to call `self._on_update()`, the `RunExecutor._broadcast_stats` method does not appear to execute.
- **Expected**: Logs showing `[STATS] Broadcasting stats...` in `RunExecutor`.
- **Actual**: No such logs appear. Only initialization logs are present.

## Suspected Root Causes
1.  **Exception Swallowing**: The `_notify` method has a broad `try/except` block that might be catching and suppressing errors raised by `_broadcast_stats` (e.g., `AttributeError` or `RuntimeError`).
2.  **Context/Scope Issue**: The `_broadcast_stats` method relies on `self._current_run_id`. If the `RunExecutor` instance context is lost or modified, this might fail.
3.  **Async/Event Loop Issue**: `_broadcast_stats` attempts to schedule an async task on the running event loop. If the loop is not accessible or closed, it might fail.

## Next Steps
1.  **Unmask Errors**: Remove the broad `try/except` in `FpfStatsTracker._notify` or add `logger.exception` to see why the callback fails.
2.  **Verify Callback Identity**: Log the `id()` of the callback function to ensure it matches the `RunExecutor` instance method.
