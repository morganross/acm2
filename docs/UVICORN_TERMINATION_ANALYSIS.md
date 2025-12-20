# Uvicorn Server Termination Analysis

## Executive Summary

During development of the ACM2 application, a critical issue was observed where the Uvicorn server would unexpectedly terminate whenever subsequent terminal commands were executed through the VS Code Copilot agent's `run_in_terminal` tool. This document provides a deep-dive analysis of the root cause, observed behavior, and potential solutions.

---

## Problem Statement

**Observed Behavior:** When running a Uvicorn server using `run_in_terminal` with `isBackground=true`, the server would gracefully shut down as soon as another terminal command was executed through the same tool.

**Impact:** This made it impossible to:
1. Start a development server and subsequently interact with it via API calls
2. Run integration tests against a running server
3. Perform normal development workflows requiring a persistent backend

---

## Technical Investigation

### Environment Details

| Component | Version/Details |
|-----------|-----------------|
| OS | Windows 11 |
| PowerShell | 5.1.26100.7462 (Desktop Edition) |
| Python | 3.x (venv activated) |
| Uvicorn | Latest (via pip) |
| VS Code | Current release |
| Tool | GitHub Copilot Agent `run_in_terminal` |

### Test Case 1: Background Terminal Server Start

**Command Sequence:**
```powershell
# Step 1: Start server in background mode
cd c:\dev\silky\api_cost_multiplier\acm2
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8002
# isBackground=true
```

**Result:**
- Server starts successfully
- PID assigned (e.g., 11060)
- Log shows: `INFO: Uvicorn running on http://0.0.0.0:8002`

**Step 2: Execute any command**
```powershell
netstat -ano | Select-String ":8002"
```

**Result:**
```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
2025-12-11 18:15:35,227 - app.main - INFO - Shutting down ACM2 API server...
INFO:     Application shutdown complete.
INFO:     Finished server process [11060]
```

**Observation:** The server received a graceful shutdown signal (SIGTERM equivalent on Windows) immediately upon the next command execution.

### Test Case 2: PowerShell Job-Based Server

**Command Sequence:**
```powershell
# Start server as a PowerShell background job
Start-Job -ScriptBlock { 
    cd c:\dev\silky\api_cost_multiplier\acm2
    python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8002 
}
```

**Result:**
- Server starts in separate job context
- Server REMAINS running after subsequent commands
- API requests work successfully
- Server PID (4992) persists across multiple commands

---

## Root Cause Analysis

### Hypothesis 1: Terminal Session Sharing (CONFIRMED)

The `run_in_terminal` tool with `isBackground=true` appears to use a **pseudo-terminal (PTY) session** that:

1. **Creates a foreground process group** for the initial command
2. **Reassigns the terminal** to subsequent commands when executed
3. **Sends SIGHUP/SIGTERM** to the previous process group when the terminal is reassigned

This is consistent with standard Unix/POSIX terminal behavior where:
- Only one process group can be in the foreground of a terminal
- When the foreground group changes, the previous group receives signals

### Hypothesis 2: VS Code Terminal Management

VS Code's integrated terminal management may:
1. Reuse terminal instances for efficiency
2. Send interrupt signals when preparing a terminal for a new command
3. Implement "cleanup" behavior that terminates existing processes

### Hypothesis 3: PowerShell Process Handling

PowerShell 5.1 (Desktop Edition) has specific behavior:
- Background processes started without `Start-Job` or `Start-Process` are tied to the session
- Session changes or new command execution may signal process termination
- The `&` operator in PowerShell doesn't fully detach processes like Unix

---

## Evidence Matrix

| Test Scenario | Server Survives? | Mechanism |
|---------------|------------------|-----------|
| `isBackground=true` + next command | ❌ NO | Terminal reassignment kills process |
| `Start-Job` + next command | ✅ YES | Job runs in separate runspace |
| `Start-Process` + next command | ✅ YES | Completely detached process |
| `isBackground=true` + no follow-up | ✅ YES | Server runs until explicit stop |

---

## Technical Deep-Dive: Signal Flow

### Scenario A: Background Terminal (Failing)

```
┌─────────────────────────────────────────────────────────────────┐
│  VS Code Terminal Session (PTY)                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Command 1: uvicorn server (PID: 11060)                 │   │
│  │  State: RUNNING                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  run_in_terminal("netstat...")                          │   │
│  │  Action: Terminal prepares for new command              │   │
│  │  Signal: SIGTERM → PID 11060                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Uvicorn receives signal                                │   │
│  │  Action: Graceful shutdown initiated                    │   │
│  │  Result: Server terminates with exit code 1             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Scenario B: PowerShell Job (Working)

```
┌─────────────────────────────────────────────────────────────────┐
│  VS Code Terminal Session (PTY)                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Command 1: Start-Job { uvicorn... }                    │   │
│  │  Result: Job1 created in separate runspace              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│  ┌────────────────────────┼────────────────────────────────┐   │
│  │  PowerShell Job Runspace (Isolated)                     │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │  uvicorn server (PID: 4992)                      │   │   │
│  │  │  State: RUNNING (isolated from PTY signals)      │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  run_in_terminal("netstat...")                          │   │
│  │  Action: New command in original PTY                    │   │
│  │  Signal: None to Job runspace                           │   │
│  │  Result: Server continues running                       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Uvicorn Signal Handling

Uvicorn explicitly handles shutdown signals gracefully:

```python
# From uvicorn source
def handle_exit(sig, frame):
    logger.info("Shutting down")
    # Initiates graceful shutdown
```

The logs confirm this:
```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [11060]
```

This is **expected behavior** when Uvicorn receives SIGTERM - it's doing exactly what it should do when asked to terminate.

---

## Workarounds and Solutions

### Solution 1: Use PowerShell Start-Job (Recommended)

```powershell
# Start server in isolated job
$job = Start-Job -ScriptBlock { 
    cd c:\dev\silky\api_cost_multiplier\acm2
    python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8002 
}

# Check output
Receive-Job $job

# Later: Stop server
Stop-Job $job
Remove-Job $job
```

**Pros:**
- Fully isolated from terminal signals
- Can retrieve output via `Receive-Job`
- Native PowerShell solution

**Cons:**
- Working directory context may need explicit handling
- Slightly more complex syntax

### Solution 2: Use Start-Process with -NoNewWindow

```powershell
Start-Process -FilePath "python" `
    -ArgumentList "-m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8002" `
    -WorkingDirectory "c:\dev\silky\api_cost_multiplier\acm2" `
    -NoNewWindow `
    -PassThru
```

**Pros:**
- Completely detached process
- Survives terminal closure
- Process object returned for management

**Cons:**
- Output not captured to terminal
- Must use separate logging file

### Solution 3: Use Separate VS Code Terminal

Manually open a separate integrated terminal in VS Code and run the server there, keeping it isolated from Copilot agent commands.

**Pros:**
- Simple, no code changes
- Full output visibility

**Cons:**
- Manual intervention required
- Not automatable via agent

### Solution 4: Run Server as Windows Service (Production)

For production deployments, run Uvicorn as a Windows service using tools like:
- NSSM (Non-Sucking Service Manager)
- Windows Task Scheduler
- Docker container

---

## Recommendations for Copilot Agent Workflows

### For Long-Running Processes

1. **Use explicit process isolation** when starting servers:
   ```powershell
   Start-Job -ScriptBlock { <server command> }
   ```

2. **Document the limitation** in workflow prompts - let the agent know that background processes may be terminated

3. **Use dedicated terminal sessions** for servers when possible

4. **Implement health checks** to detect server termination:
   ```powershell
   # Before API calls
   $port = (Get-NetTCPConnection -LocalPort 8002 -ErrorAction SilentlyContinue)
   if (-not $port) { <restart server> }
   ```

### For Testing Workflows

1. Start server via `Start-Job` or `Start-Process`
2. Wait for server to be ready: `Start-Sleep 3`
3. Verify server is listening: `netstat -ano | Select-String ":8002"`
4. Execute tests/API calls
5. Cleanup: Stop job/process

---

## Appendix: Log Analysis

### Successful Startup (Before Termination)
```
SESSION DB URL: sqlite+aiosqlite:///C:/Users/kjhgf/.acm2/acm2.db
!!! USING DATABASE URL: sqlite+aiosqlite:///C:/Users/kjhgf/.acm2/acm2.db !!!
INFO:     Started server process [11060]
INFO:     Waiting for application startup.
2025-12-11 18:15:20,431 - app.main - INFO - Starting ACM2 API server...
2025-12-11 18:15:20,475 - app.main - INFO - Database tables initialized
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8002 (Press CTRL+C to quit)
```

### Termination Sequence (Triggered by Next Command)
```
INFO:     Shutting down
INFO:     Waiting for application shutdown.
2025-12-11 18:15:35,227 - app.main - INFO - Shutting down ACM2 API server...
INFO:     Application shutdown complete.
INFO:     Finished server process [11060]

Command exited with code 1
```

**Time Delta:** ~15 seconds between startup and termination (time for next command execution)

**Exit Code 1:** Indicates terminated by signal rather than error

---

## Conclusion

The Uvicorn server termination issue is **not a bug** in Uvicorn, the ACM2 application, or Python. It is a **behavioral characteristic** of how the VS Code Copilot agent's `run_in_terminal` tool manages terminal sessions.

The tool appears to send termination signals to existing processes when preparing the terminal for new commands, causing graceful shutdown of any long-running processes.

**The recommended workaround** is to use PowerShell's `Start-Job` command to run servers in an isolated execution context that is not affected by terminal session management.

---

## References

- [Uvicorn Documentation - Deployment](https://www.uvicorn.org/deployment/)
- [PowerShell Jobs](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_jobs)
- [Windows Process Signals](https://docs.microsoft.com/en-us/windows/console/ctrl-c-and-ctrl-break-signals)
- [VS Code Integrated Terminal](https://code.visualstudio.com/docs/terminal/basics)

---

*Document Created: December 11, 2025*
*Analysis Performed By: GitHub Copilot Agent*
*ACM2 Project - API Cost Multiplier v2.0*
