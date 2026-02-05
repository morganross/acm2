# Chat Rules - Terminal Command Execution

## Problem
When Copilot chat is stopped/interrupted, terminal commands that are running get killed. This causes long-running commands like `pip install` to fail mid-execution.

## Solution: Use Background Mode for Long-Running Commands

### For commands that take more than a few seconds:
1. Use `isBackground: true` in `run_in_terminal`
2. This returns immediately with a terminal ID
3. The command continues running even if chat is stopped
4. Use `get_terminal_output` with the terminal ID to check progress later

### For commands that need PATH or environment setup:
1. Set PATH at the start of the SAME command (semicolon-separated)
2. Example: `$env:Path = "C:\Program Files\Python311;" + $env:Path; pip install -e .`
3. Each terminal session is independent - PATH must be set each time

### Alternative: Write to a script file first
For complex or very long commands:
1. Create a `.ps1` script file with all commands
2. Run the script file as background process
3. Log output to a file for later review

Example:
```powershell
# Create script
Set-Content -Path "c:\devlop\install.ps1" -Value @'
$env:Path = "C:\Program Files\Python311;C:\Program Files\Python311\Scripts;" + $env:Path
cd c:\devlop\acm2\acm2
pip install -e . 2>&1 | Out-File c:\devlop\pip_install.log
'@

# Run script in background
Start-Process powershell -ArgumentList "-File", "c:\devlop\install.ps1" -NoNewWindow
```

## Key Rules
1. **Long commands** → `isBackground: true`
2. **Environment setup** → Include in same command line, not separate calls
3. **Check results** → Use log files or `get_terminal_output`
4. **New terminals don't inherit PATH** → Always set PATH explicitly if needed


YOU ARE ROBIDDEN FROM RUNNING COMMANDS THAT ARE INTERUPTABLE BY CO PILOT.
IT IS POSSIBLE TO RUN COMMANDS IN A WAY THAT ARE UNINTENTIONALLY STOPPED WHEN CO PILOT CHAT STOPS.
TERMIAL COMMANDS MUST CONTINUE NO MATTER WHAT CO PILOT IS DOING.

# Running ACM2 Servers

## Backend Server (This Machine - 54.71.183.56)

**MANDATORY**: Use the unified restart script:

```powershell
# Normal restart (clears caches, keeps user data)
c:\devlop\acm2\restart.ps1

# DESTRUCTIVE: Delete all user data and restart fresh
c:\devlop\acm2\restart.ps1 -Purge
```

This script:
1. Stops any running ACM2 server
2. Clears all Python caches (__pycache__, .pyc files)
3. Checkpoints SQLite databases (prevents corruption)
4. Optionally purges all user data (-Purge flag)
5. Starts server DETACHED in hidden window (survives VS Code interruptions)
6. Logs to `c:\devlop\acm2\server.log`

## Backend Configuration
- **Port**: 443 (HTTPS with SSL)
- **Host**: 0.0.0.0 (accessible from outside)
- **Location**: c:\devlop\acm2\acm2
- **Python**: C:\Program Files\Python311
- **SSL Certs**: c:\devlop\acm2\certs\cloudflare.crt/.key

## Frontend Server (WordPress/Bitnami - 35.88.196.59)

**NOTE**: Frontend is on a SEPARATE server. Restart via SSH:

```bash
ssh ubuntu@35.88.196.59 'sudo /opt/bitnami/ctlscript.sh restart apache'
```

Or using Python Paramiko (recommended for Copilot):
```python
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('35.88.196.59', username='ubuntu', key_filename='C:/Users/Administrator/.ssh/acm2-frontend.pem')
stdin, stdout, stderr = ssh.exec_command('sudo /opt/bitnami/ctlscript.sh restart apache')
print(stdout.read().decode())
ssh.close()
```

## Utility Commands

### Check Backend Status
```powershell
Get-NetTCPConnection -LocalPort 443 -ErrorAction SilentlyContinue
```

### View Backend Logs
```powershell
Get-Content c:\devlop\acm2\server.log -Wait -Tail 50
```

### Kill Backend (if needed)
```powershell
Get-NetTCPConnection -LocalPort 443 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## ⚠️ DO NOT start the server manually
Always use `restart.ps1` - it ensures caches are cleared and server runs detached.
