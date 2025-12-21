# ACM2 Logging Regression Report

## Executive Summary
We have identified the root cause of the recurring issue where runs execute with `INFO` level logging despite being configured for `VERBOSE` (Debug) mode. While recent fixes successfully isolated log files to prevent "zombie" process interference, they failed to address the global filtering rules that govern which messages are allowed to be generated in the first place.

## The Problem: The "Gatekeeper" Effect
To understand why this is happening, imagine the logging system as a security checkpoint with two gates:

1.  **The Main Gate (Root Logger)**: This is the global setting for the entire application. Currently, it is hardcoded to `INFO`. This means it blocks any "Debug" or "Verbose" messages from ever entering the building.
2.  **The Office Door (File Handler)**: This is the specific log file for a run. We have correctly set this to accept `DEBUG` messages.

**The Conflict:**
Even though the Office Door (File Handler) is wide open and ready to accept Verbose logs, the Main Gate (Root Logger) is turning them away at the entrance. The application generates a Debug message, the Root Logger sees it is below the `INFO` threshold, and discards it immediately. It never reaches your run's log file.

## Why This Keeps Happening
This issue has persisted through multiple refactors because our fixes have focused on **isolation** rather than **permission**.
*   **Fix 1 (Previous)**: We ensured runs write to separate folders.
*   **Fix 2 (Recent)**: We ensured runs don't write to each other's files (Context-Aware Logging).

However, we never updated the application startup logic to lower the "Main Gate" threshold. Because Python's logging system is a global singleton, developers are often hesitant to change the global level for fear of flooding the console. This caution has resulted in the `INFO` restriction remaining in place, silently overriding your Preset configurations.

## The Solution
To permanently fix this, we must invert the control logic:
1.  **Open the Main Gate**: The global Root Logger must be set to `DEBUG` (or the lowest possible level) at startup. This allows all messages to flow through the system.
2.  **Guard the Doors**: We rely on the individual File Handlers (which we just fixed with Context Filters) to decide what to keep.
    *   If a Run is set to `INFO`, its handler will ignore the extra noise.
    *   If a Run is set to `VERBOSE`, its handler will capture the full detail.

This approach allows per-run granularity without the global "INFO" setting acting as a bottleneck.
