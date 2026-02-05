# How to Start a Service - Command Execution Methods

Based on the chat_rules.md file, here are **all the different ways to run commands**:

---

## 1. **Normal Terminal Command (Interruptible)**
- Standard `run_in_terminal` with `isBackground: false`
- **Problem**: Gets killed when Copilot chat stops
- **Use for**: Quick commands under 5 seconds

---

## 2. **Background Terminal Command**
- `run_in_terminal` with `isBackground: true`
- Returns immediately with a terminal ID
- Use `get_terminal_output` to check progress later
- **Problem**: Still runs inside VS Code terminal - may still get interrupted in some cases
- **Use for**: Commands that take more than a few seconds

---

## 3. **Start-Process (Separate Window)**
- `Start-Process powershell -ArgumentList "command"`
- Spawns a completely separate PowerShell window
- Survives VS Code/Copilot interruptions
- **Problem**: Opens a visible window
- **Use for**: Long-running servers

---

## 4. **Start-Process with Hidden Window**
- `Start-Process powershell -ArgumentList "command" -WindowStyle Hidden`
- Runs in background with no visible window
- Completely detached from VS Code
- **Use for**: Background services that should be invisible

---

## 5. **Start-Process with -NoNewWindow**
- `Start-Process powershell -ArgumentList "-File", "script.ps1" -NoNewWindow`
- Runs without creating a new window
- Output goes nowhere (or to a log file if redirected in script)
- **Use for**: Fire-and-forget background tasks

---

## 6. **Write Script File Then Execute**
- Create a `.ps1` file with all commands
- Run the script file as a separate process
- Log output to a file for later review
- **Best for**: Complex multi-step operations, ensures full command survives

---

## 7. **Start-Job (PowerShell Job)**
- `Start-Job -ScriptBlock { commands }`
- Runs as a PowerShell background job
- Can check status with `Get-Job`, output with `Receive-Job`
- **Problem**: Jobs are tied to the PowerShell session - if session ends, job dies
- **Use for**: Background tasks within same session

---

## 8. **Scheduled Task (Task Scheduler)**
- Create a Windows Task Scheduler task
- Runs completely independent of any terminal
- Survives reboots, user logoff, everything
- **Use for**: Services that must always run

---

## 9. **NSSM (Windows Service)**
- Install as a proper Windows service using Non-Sucking Service Manager
- Runs at system level, auto-restarts on failure
- **Use for**: Production services that need maximum reliability

---

## Summary: What's Best for ACM2 Server

For an **uninterruptible ACM2 server**, the best options are:

1. **Start-Process with -WindowStyle Hidden** - Quick to set up, fully detached
2. **Write to script file, then Start-Process the script** - Most reliable, easy to debug via log files
3. **NSSM as Windows Service** - Best for production, but more setup

The `restart.ps1` script uses option 2: writes a launcher script then launches it detached with `Start-Process -WindowStyle Hidden`.
