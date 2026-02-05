# =============================================================================
# ACM2 BACKEND RESTART SCRIPT
# =============================================================================
# The ONE script to restart the ACM2 backend server.
#
# Usage:
#   .\restart.ps1           - Normal restart (clears caches, keeps data)
#   .\restart.ps1 -Purge    - DESTRUCTIVE: Deletes all user data, fresh install
#
# The server runs DETACHED in a hidden window, survives VS Code interruptions.
# Logs go to: c:\devlop\acm2\server.log
#
# NOTE: Frontend (WordPress/Bitnami) is on a separate server.
#       Restart frontend via SSH: sudo /opt/bitnami/ctlscript.sh restart apache
# =============================================================================

param(
    [switch]$Purge = $false
)

$ErrorActionPreference = "SilentlyContinue"

# Configuration
$ACM2_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ACM2_APP = Join-Path $ACM2_ROOT "acm2"
$DATA_DIR = Join-Path $ACM2_APP "data"
$CERTS_DIR = Join-Path $ACM2_ROOT "certs"
$LOG_FILE = Join-Path $ACM2_ROOT "server.log"
$SSL_CERT = Join-Path $CERTS_DIR "cloudflare.crt"
$SSL_KEY = Join-Path $CERTS_DIR "cloudflare.key"
$PYTHON_PATH = "C:\Program Files\Python311"
$ACM2_PORT = 443

# Ensure Python is in PATH
$env:Path = "$PYTHON_PATH;$PYTHON_PATH\Scripts;" + $env:Path

# Header
Write-Host ""
if ($Purge) {
    Write-Host "=============================================" -ForegroundColor Red
    Write-Host "  ACM2 RESTART - PURGE MODE" -ForegroundColor Red
    Write-Host "  WARNING: ALL USER DATA WILL BE DELETED!" -ForegroundColor Red
    Write-Host "=============================================" -ForegroundColor Red
} else {
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "  ACM2 BACKEND RESTART" -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
}
Write-Host ""

# -----------------------------------------------------------------------------
# STEP 1: Stop existing server
# -----------------------------------------------------------------------------
Write-Host "[1/5] Stopping ACM2 backend server..." -ForegroundColor Yellow

$serverProcess = Get-NetTCPConnection -LocalPort $ACM2_PORT -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq 'Listen' } | 
    Select-Object -ExpandProperty OwningProcess -First 1

if ($serverProcess) {
    Stop-Process -Id $serverProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "       Stopped server (PID: $serverProcess)" -ForegroundColor Green
} else {
    Write-Host "       Server was not running" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# STEP 2: Clear Python caches
# -----------------------------------------------------------------------------
Write-Host "[2/5] Clearing Python caches..." -ForegroundColor Yellow

$pycacheDirs = Get-ChildItem -Path $ACM2_ROOT -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
$pycCount = 0
foreach ($dir in $pycacheDirs) {
    Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $pycCount++
}

$pycFiles = Get-ChildItem -Path $ACM2_ROOT -Include "*.pyc" -Recurse -File -Force -ErrorAction SilentlyContinue
$pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "       Removed $pycCount __pycache__ directories" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 3: Checkpoint SQLite databases (prevents corruption)
# -----------------------------------------------------------------------------
Write-Host "[3/5] Checkpointing SQLite databases..." -ForegroundColor Yellow

$sqliteCount = 0
$dbFiles = Get-ChildItem -Path $DATA_DIR -Filter "*.db" -ErrorAction SilentlyContinue
foreach ($db in $dbFiles) {
    $checkpointScript = @"
import sqlite3
try:
    conn = sqlite3.connect('$($db.FullName -replace '\\', '/')')
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
except: pass
"@
    $tempFile = "$env:TEMP\checkpoint_$($db.BaseName).py"
    [System.IO.File]::WriteAllText($tempFile, $checkpointScript, [System.Text.UTF8Encoding]::new($false))
    & python $tempFile 2>&1 | Out-Null
    Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    $sqliteCount++
}
Write-Host "       Checkpointed $sqliteCount databases" -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 4: PURGE MODE - Delete all user data (if -Purge flag)
# -----------------------------------------------------------------------------
if ($Purge) {
    Write-Host "[4/5] PURGING ALL USER DATA..." -ForegroundColor Red
    
    # Delete user databases
    $userDbs = Get-ChildItem -Path $DATA_DIR -Filter "user_*.db" -ErrorAction SilentlyContinue
    $deletedCount = 0
    foreach ($db in $userDbs) {
        Remove-Item $db.FullName -Force
        $walFile = $db.FullName + "-wal"
        $shmFile = $db.FullName + "-shm"
        if (Test-Path $walFile) { Remove-Item $walFile -Force }
        if (Test-Path $shmFile) { Remove-Item $shmFile -Force }
        $deletedCount++
    }
    Write-Host "       Deleted $deletedCount user database(s)" -ForegroundColor Red
    
    # Delete legacy master.db if exists
    $masterDb = Join-Path $DATA_DIR "master.db"
    if (Test-Path $masterDb) {
        Remove-Item $masterDb -Force
        Remove-Item "$masterDb-wal" -Force -ErrorAction SilentlyContinue
        Remove-Item "$masterDb-shm" -Force -ErrorAction SilentlyContinue
        Write-Host "       Deleted master.db (legacy)" -ForegroundColor Red
    }
    
    # Clear old log
    if (Test-Path $LOG_FILE) {
        Remove-Item $LOG_FILE -Force
        Write-Host "       Deleted old server.log" -ForegroundColor Red
    }
} else {
    Write-Host "[4/5] Keeping user data (use -Purge to delete)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# STEP 5: Start server DETACHED (survives VS Code interruptions)
# -----------------------------------------------------------------------------
Write-Host "[5/5] Starting ACM2 backend server (detached)..." -ForegroundColor Yellow

# Verify SSL certs exist
if (-not (Test-Path $SSL_CERT)) {
    Write-Host "       ERROR: SSL cert not found: $SSL_CERT" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $SSL_KEY)) {
    Write-Host "       ERROR: SSL key not found: $SSL_KEY" -ForegroundColor Red
    exit 1
}

# Create a launcher script that will run detached
$launcherScript = Join-Path $ACM2_ROOT "server_launcher.ps1"
$launcherContent = @"
# Auto-generated launcher script - DO NOT EDIT
Set-Location '$ACM2_APP'
`$env:Path = '$PYTHON_PATH;$PYTHON_PATH\Scripts;' + `$env:Path
python -u -m uvicorn app.main:app ``
    --host 0.0.0.0 ``
    --port $ACM2_PORT ``
    --ssl-keyfile '$SSL_KEY' ``
    --ssl-certfile '$SSL_CERT' ``
    2>&1 | Tee-Object -FilePath '$LOG_FILE'
"@
Set-Content -Path $launcherScript -Value $launcherContent -Force

# Start the server in a HIDDEN window (completely detached)
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$launcherScript`"" -WindowStyle Hidden

# Wait for server to start
Write-Host "       Waiting for server to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Verify server is running
$serverRunning = Get-NetTCPConnection -LocalPort $ACM2_PORT -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq 'Listen' }

if ($serverRunning) {
    $pid = ($serverRunning | Select-Object -First 1).OwningProcess
    Write-Host "       Server started on port $ACM2_PORT with SSL (PID: $pid)" -ForegroundColor Green
} else {
    Write-Host "       Server may still be starting..." -ForegroundColor Yellow
    Write-Host "       Check log: Get-Content '$LOG_FILE' -Tail 50" -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  RESTART COMPLETE" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend URL:  https://54.71.183.56" -ForegroundColor Cyan
Write-Host "  Log file:     $LOG_FILE" -ForegroundColor Cyan
Write-Host "  Data dir:     $DATA_DIR" -ForegroundColor Cyan
Write-Host ""
Write-Host "  View logs:    Get-Content '$LOG_FILE' -Wait -Tail 50" -ForegroundColor White
Write-Host "  Stop server:  Get-NetTCPConnection -LocalPort 443 | ForEach-Object { Stop-Process -Id `$_.OwningProcess -Force }" -ForegroundColor White
Write-Host ""
Write-Host "  Frontend (WordPress/Bitnami) is on a SEPARATE server." -ForegroundColor Yellow
Write-Host "  Restart frontend via SSH:" -ForegroundColor Yellow
Write-Host "    ssh ubuntu@35.88.196.59 'sudo /opt/bitnami/ctlscript.sh restart apache'" -ForegroundColor White
Write-Host ""
