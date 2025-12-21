# Plan: Complete Removal of Global Logging for Runs

## Objective
Eliminate all dependencies on the Python Global Root Logger for run execution. Ensure that the logging level selected in the GUI is the **absolute and only authority** for a run's logs, with zero interference from system defaults or other runs.

## Core Concept: Private Run Loggers
Instead of attaching handlers to the shared `logging.getLogger()`, we will instantiate a dedicated, isolated logger for each unique run ID.

## Implementation Steps

### 1. Create the `RunLogger` Factory
We will create a utility that generates a detached logger instance.
*   **Input**: `run_id`, `log_level` (from GUI).
*   **Action**:
    *   Create a logger named `run.{run_id}`.
    *   **CRITICAL**: Set `logger.propagate = False`. This cuts the cord to the global system.
    *   Set the level strictly to the user's choice.
    *   Attach the File Handler for the run's log folder.
*   **Output**: A clean, isolated logger object.

### 2. Update `RunExecutor` to Use Private Logger
The `RunExecutor` service currently relies on `logging.getLogger(__name__)`. This must change.
*   **Change**: The `execute` method will initialize the private `RunLogger` at the very start.
*   **Usage**: Pass this logger instance down to all helper methods (`_generate`, `_evaluate`, etc.).
*   **Refactor**: Replace all `logger.info(...)` calls inside the executor to use `self.run_logger.info(...)`.

### 3. Update `FpfAdapter` and Subprocesses
The FPF adapter currently logs to the global system.
*   **Change**: Pass the private `run_logger` into the adapter.
*   **Subprocess**: The FPF subprocess script (`fpf_main.py`) is a separate process, so it needs its own arguments.
    *   Pass the log level explicitly via command line or env var: `FPF_LOG_LEVEL={user_choice}`.
    *   Ensure `fpf_main.py` initializes its *own* internal logger to match that level exactly.

### 4. Clean Up `app/api/routes/runs.py`
*   **Remove**: Delete the code that attaches `FileHandler` to `root_logger`.
*   **Remove**: Delete the `RunContextFilter` (it's no longer needed because the loggers are physically separate objects).
*   **Simplify**: The route simply passes the config to the executor. The executor handles the logging setup internally.

## Verification
1.  **Isolation Check**: Start a run with `VERBOSE`. Start another with `INFO`.
2.  **Level Check**: Verify `run_A.log` contains DEBUG messages. Verify `run_B.log` does NOT.
3.  **Global Check**: Verify that system startup logs (Uvicorn/FastAPI) do NOT appear in the run logs.

## Outcome
*   **Zero Global State**: Run logs are private objects.
*   **Zero Fallbacks**: The level is set once, explicitly, on the private object.
*   **Zero Interference**: No "Main Valve" to restrict flow.
