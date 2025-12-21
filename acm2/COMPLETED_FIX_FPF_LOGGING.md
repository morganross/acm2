# Completed: Fix FPF Log Contention (Option 1)

## Summary
Implemented "Parent-Directed Logging" to resolve the file locking contention that caused FPF subprocesses to hang and timeout on Windows.

## Changes Implemented

### 1. `FilePromptForge/fpf_main.py`
*   **Added Argument**: Added `--log-file` argument to the CLI parser.
*   **Updated Logging Setup**: Modified `setup_logging` to accept a log file path and clear existing handlers before re-configuring.
*   **Logic**: If `--log-file` is provided, FPF uses that specific file for its internal `logging` module output. If not, it falls back to the default PID-based filename.

### 2. `acm2/app/adapters/fpf/adapter.py`
*   **Updated `generate`**: Logic added to derive a unique log filename (`fpf_{task_id}.log`) from the provided `run_log_file` path.
*   **Updated `_build_fpf_command`**: Accepts the `log_file` path and appends `--log-file <path>` to the subprocess command.

## Result
*   **Isolation**: Each FPF task now writes to a unique file (e.g., `logs/{run_id}/fpf_{task_id}.log`).
*   **Organization**: All logs (main run log + individual FPF task logs) are stored in the same run-specific directory.
*   **Safety**: Eliminates the race condition where multiple processes fought over `fpf_run.log`.
