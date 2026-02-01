# =============================================================================
# PURGE AND RESTART SCRIPT
# =============================================================================
# Deletes all user data, databases, and restarts the backend as a fresh install.
# This is a DESTRUCTIVE operation - all user data will be lost!
# =============================================================================

Write-Host ""
Write-Host "=============================================" -ForegroundColor Red
Write-Host "  ACM2 PURGE AND RESTART SCRIPT" -ForegroundColor Red
Write-Host "  WARNING: This will DELETE ALL USER DATA!" -ForegroundColor Red
Write-Host "=============================================" -ForegroundColor Red
Write-Host ""

$acm2Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dataDir = Join-Path $acm2Root "acm2\data"
$logFile = Join-Path $acm2Root "server.log"

Write-Host "[1/7] Stopping ACM2 backend server..." -ForegroundColor Yellow
$uvicornProcess = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq 'Listen' } | 
    Select-Object -ExpandProperty OwningProcess -First 1

if ($uvicornProcess) {
    Stop-Process -Id $uvicornProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Write-Host "        Backend stopped (PID: $uvicornProcess)" -ForegroundColor Green
} else {
    Write-Host "        Backend was not running" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[2/7] Deleting master.db (DEPRECATED - no longer used)..." -ForegroundColor Yellow
$masterDb = Join-Path $dataDir "master.db"
if (Test-Path $masterDb) {
    Remove-Item $masterDb -Force
    Write-Host "        Deleted: $masterDb (legacy file)" -ForegroundColor Green
} else {
    Write-Host "        master.db does not exist (not used in new architecture)" -ForegroundColor Gray
}

# Also delete WAL and SHM files if they exist
$masterDbWal = Join-Path $dataDir "master.db-wal"
$masterDbShm = Join-Path $dataDir "master.db-shm"
if (Test-Path $masterDbWal) { Remove-Item $masterDbWal -Force }
if (Test-Path $masterDbShm) { Remove-Item $masterDbShm -Force }

Write-Host ""
Write-Host "[3/7] Deleting all user databases (user_*.db)..." -ForegroundColor Yellow
$userDbs = Get-ChildItem -Path $dataDir -Filter "user_*.db" -ErrorAction SilentlyContinue
if ($userDbs) {
    $count = $userDbs.Count
    foreach ($db in $userDbs) {
        Remove-Item $db.FullName -Force
        $walFile = $db.FullName + "-wal"
        $shmFile = $db.FullName + "-shm"
        if (Test-Path $walFile) { Remove-Item $walFile -Force }
        if (Test-Path $shmFile) { Remove-Item $shmFile -Force }
    }
    Write-Host "        Deleted $count user database(s)" -ForegroundColor Green
} else {
    Write-Host "        No user databases found (already clean)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[4/7] Clearing Python __pycache__ directories..." -ForegroundColor Yellow
$pycacheDirs = Get-ChildItem -Path $acm2Root -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($pycacheDirs) {
    $count = $pycacheDirs.Count
    $pycacheDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "        Removed $count __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "        No __pycache__ directories found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[5/7] Clearing old server log..." -ForegroundColor Yellow
if (Test-Path $logFile) {
    Remove-Item $logFile -Force
    Write-Host "        Deleted old server.log" -ForegroundColor Green
} else {
    Write-Host "        No old log file found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[6/7] Verifying .env configuration..." -ForegroundColor Yellow
$envFile = Join-Path $acm2Root "acm2\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    Write-Host "        .env file found" -ForegroundColor Green
    
    if ($envContent -match "ENCRYPTION_KEY=") {
        Write-Host "        + ENCRYPTION_KEY is set" -ForegroundColor Green
    } else {
        Write-Host "        X ENCRYPTION_KEY is MISSING!" -ForegroundColor Red
    }
    
    if ($envContent -match "ACM2_PLUGIN_SECRET=") {
        Write-Host "        + ACM2_PLUGIN_SECRET is set" -ForegroundColor Green
    } else {
        Write-Host "        X ACM2_PLUGIN_SECRET is MISSING!" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "        Current .env content:" -ForegroundColor Cyan
    Write-Host "        ------------------------" -ForegroundColor Cyan
    Get-Content $envFile | ForEach-Object { Write-Host "        $_" -ForegroundColor Gray }
    Write-Host "        ------------------------" -ForegroundColor Cyan
} else {
    Write-Host "        X .env file NOT FOUND at $envFile" -ForegroundColor Red
    Write-Host "        Creating default .env file..." -ForegroundColor Yellow
    
    $defaultEnv = @"
# Required
ENCRYPTION_KEY=RLDJ1CTjZ8A6MaR1kYsrMvBdY_MfbKVegaHTRxzDJb0=
SEED_PRESET_ID=86f721fc-742c-4489-9626-f148cb3d6209
SEED_VERSION=1.0.0
ACM2_PLUGIN_SECRET=sk_plugin_your_secret_here
"@
    Set-Content -Path $envFile -Value $defaultEnv
    Write-Host "        Created .env with default values" -ForegroundColor Green
}

Write-Host ""
Write-Host "[7/7] Starting ACM2 backend server with logging to file..." -ForegroundColor Yellow
$appDir = Join-Path $acm2Root "acm2"

$pythonPath = "C:\Program Files\Python311\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

Write-Host "        Log file: $logFile" -ForegroundColor Cyan
Write-Host "        Starting server..." -ForegroundColor Cyan

# Start server with output redirected to log file
$job = Start-Job -ScriptBlock {
    param($python, $workDir, $log)
    Set-Location $workDir
    & $python -u -m uvicorn app.main:app --host 0.0.0.0 --port 80 --log-level debug 2>&1 | Tee-Object -FilePath $log
} -ArgumentList $pythonPath, $appDir, $logFile

Start-Sleep -Seconds 5

# Verify server started
$serverRunning = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq 'Listen' }

if ($serverRunning) {
    $pid = (Get-NetTCPConnection -LocalPort 80 | Where-Object { $_.State -eq 'Listen' } | Select-Object -First 1).OwningProcess
    Write-Host "        ACM2 server started on port 80 (PID: $pid)" -ForegroundColor Green
} else {
    Write-Host "        X Failed to start ACM2 server!" -ForegroundColor Red
    Write-Host "        Check $logFile for errors" -ForegroundColor Red
    
    if (Test-Path $logFile) {
        Write-Host ""
        Write-Host "        Last 30 lines of log:" -ForegroundColor Yellow
        Get-Content $logFile -Tail 30 | ForEach-Object { Write-Host "        $_" -ForegroundColor Gray }
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  PURGE COMPLETE - FRESH INSTALL STATE" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Data directory: $dataDir" -ForegroundColor Cyan
Write-Host "  Log file: $logFile" -ForegroundColor Cyan
Write-Host "  Status:" -ForegroundColor Cyan
Write-Host "    - master.db: DELETED (will be recreated on first request)" -ForegroundColor White
Write-Host "    - user_*.db: DELETED" -ForegroundColor White
Write-Host "    - Plugin secret: One-time use enabled" -ForegroundColor White
Write-Host ""
Write-Host "  To view logs in real-time:" -ForegroundColor Yellow
Write-Host "    Get-Content $logFile -Wait -Tail 50" -ForegroundColor White
Write-Host ""
