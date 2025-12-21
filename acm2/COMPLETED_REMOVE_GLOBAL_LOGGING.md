# Completed: Remove Global Logging Dependency

## Summary
We have successfully refactored the logging architecture to use **Private Run Loggers**. This eliminates the "INFO level leak" where the global root logger suppressed DEBUG logs from runs, and prevents "zombie" processes from logging to the wrong files.

## Changes Implemented

### 1. `app/utils/logging_utils.py`
*   **Removed**: `RunContextFilter` and `run_context`.
*   **Added**: `get_run_logger(run_id, log_file_path, level_name)` factory function.
    *   Creates a logger named `run.{run_id}`.
    *   Sets `propagate = False` to detach from root logger.
    *   Sets level explicitly based on arguments.
    *   Adds a `FileHandler` pointing to the run's log file.

### 2. `app/services/run_executor.py`
*   **Refactored**: `RunExecutor` class now accepts an optional `run_logger` in `__init__`.
*   **Updated**: Replaced all usages of the global `logger` with `self.logger`.
*   **Fallback**: If no logger is provided (e.g. in tests), it falls back to `logging.getLogger(__name__)`.

### 3. `app/api/routes/runs.py`
*   **Updated**: `execute_run_background` now uses `get_run_logger` to create the logger.
*   **Updated**: Passes the private logger to `RunExecutor`.
*   **Cleanup**: Properly closes handlers attached to the private logger after the run completes.
*   **Removed**: Logic that attached handlers to the root logger.

## Verification
*   **Isolation**: Each run now writes to its own file via a detached logger.
*   **Levels**: The log level is set on the private logger, ignoring the global root logger's level.
*   **Safety**: Handlers are closed to prevent file locks.

## Next Steps
*   Run a test execution to verify logs appear in `logs/{run_id}/run.log` with the correct level.
