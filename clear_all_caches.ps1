# ============================================================================
# CACHE DESTRUCTION SCRIPT - FULLY AUTOMATIC
# ============================================================================
# RUN THIS SCRIPT:
#   - AFTER EVERY CODE CHANGE
#   - BEFORE EVERY TEST
#   - NO EXCEPTIONS
#
# This script clears ALL caches and AUTOMATICALLY restarts ACM2.
# There is NO human interaction - it runs completely unattended.
#
# Usage: .\clear_all_caches.ps1
# ============================================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CACHE DESTRUCTION SCRIPT" -ForegroundColor Cyan
Write-Host "  Fully Automatic - No Interaction" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "SilentlyContinue"
$cleared = 0
$failed = 0

# Configuration
$ACM2_ROOT = "c:\devlop\acm2"
$ACM2_APP = "$ACM2_ROOT\acm2"
$PYTHON_PATH = "C:\Program Files\Python311"
$ACM2_PORT = 80

# Ensure Python is in PATH
$env:Path = "$PYTHON_PATH;$PYTHON_PATH\Scripts;" + $env:Path

# ----------------------------------------------------------------------------
# 1. PYTHON __pycache__ DIRECTORIES
# ----------------------------------------------------------------------------
Write-Host "[1/8] Clearing Python __pycache__ directories..." -ForegroundColor Yellow

$pycacheDirs = Get-ChildItem -Path $ACM2_ROOT -Include "__pycache__" -Recurse -Directory -Force
$pycCount = 0
foreach ($dir in $pycacheDirs) {
    Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $pycCount++
}
Write-Host "       Removed $pycCount __pycache__ directories" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 2. PYTHON .pyc FILES (in case any are loose)
# ----------------------------------------------------------------------------
Write-Host "[2/8] Clearing loose .pyc files..." -ForegroundColor Yellow

$pycFiles = Get-ChildItem -Path $ACM2_ROOT -Include "*.pyc" -Recurse -File -Force
$pycFileCount = $pycFiles.Count
$pycFiles | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "       Removed $pycFileCount .pyc files" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 3. VITE/NPM BUILD CACHE (if UI exists)
# ----------------------------------------------------------------------------
Write-Host "[3/8] Clearing Vite/npm caches..." -ForegroundColor Yellow

$viteCachePaths = @(
    "$ACM2_ROOT\ui\node_modules\.vite",
    "$ACM2_ROOT\ui\.vite_temp",
    "$ACM2_APP\ui\node_modules\.vite"
)

$viteCleared = 0
foreach ($path in $viteCachePaths) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        $viteCleared++
    }
}
Write-Host "       Cleared $viteCleared Vite cache directories" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 4. SQLITE WAL CHECKPOINTS
# ----------------------------------------------------------------------------
Write-Host "[4/8] Checkpointing SQLite databases..." -ForegroundColor Yellow

$sqlitePaths = @(
    "$ACM2_APP\data",
    "$env:USERPROFILE\.acm2"
)
$sqliteCount = 0
foreach ($sqlitePath in $sqlitePaths) {
    if (Test-Path $sqlitePath) {
        $sqliteFiles = Get-ChildItem -Path $sqlitePath -Filter "*.db" -ErrorAction SilentlyContinue
        foreach ($db in $sqliteFiles) {
            $pythonCheckpoint = @"
import sqlite3
try:
    conn = sqlite3.connect('$($db.FullName -replace '\\', '/')')
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
except: pass
"@
            $tempPyFile = "$env:TEMP\sqlite_checkpoint.py"
            [System.IO.File]::WriteAllText($tempPyFile, $pythonCheckpoint, [System.Text.UTF8Encoding]::new($false))
            & python $tempPyFile 2>&1 | Out-Null
            Remove-Item $tempPyFile -Force -ErrorAction SilentlyContinue
            $sqliteCount++
        }
    }
}
Write-Host "       Checkpointed $sqliteCount SQLite databases" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 5. TYPESCRIPT BUILD INFO (if any)
# ----------------------------------------------------------------------------
Write-Host "[5/8] Clearing TypeScript build caches..." -ForegroundColor Yellow

$tsBuildInfoFiles = Get-ChildItem -Path $ACM2_ROOT -Include "*.tsbuildinfo", "tsconfig.tsbuildinfo" -Recurse -File -Force
$tsCount = $tsBuildInfoFiles.Count
$tsBuildInfoFiles | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "       Removed $tsCount TypeScript build info files" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 6. WINDOWS DNS CACHE
# ----------------------------------------------------------------------------
Write-Host "[6/8] Flushing Windows DNS cache..." -ForegroundColor Yellow

ipconfig /flushdns 2>&1 | Out-Null
Write-Host "       Windows DNS cache flushed" -ForegroundColor Green
$cleared++

# ----------------------------------------------------------------------------
# 7. STOP ACM2 UVICORN SERVER
# ----------------------------------------------------------------------------
Write-Host "[7/8] Stopping ACM2 backend server..." -ForegroundColor Yellow

# Kill any process using the configured port
$portProcess = Get-NetTCPConnection -LocalPort $ACM2_PORT -ErrorAction SilentlyContinue
if ($portProcess) {
    foreach ($conn in $portProcess) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    Write-Host "       ACM2 server stopped (was on port $ACM2_PORT)" -ForegroundColor Green
} else {
    Write-Host "       ACM2 server was not running" -ForegroundColor Green
}
$cleared++

# ----------------------------------------------------------------------------
# 8. START ACM2 UVICORN SERVER (requires admin for port 80)
# ----------------------------------------------------------------------------
Write-Host "[8/8] Starting ACM2 backend server..." -ForegroundColor Yellow

# Start ACM2 in a new elevated PowerShell window (persists after script ends)
$acm2StartScript = @"
`$env:Path = '$PYTHON_PATH;$PYTHON_PATH\Scripts;' + `$env:Path
Set-Location '$ACM2_APP'
python cli.py serve
"@

# Port 80 requires admin privileges
Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-Command", $acm2StartScript -WindowStyle Minimized
Start-Sleep -Seconds 5

# Verify it started
$serverUp = Get-NetTCPConnection -LocalPort $ACM2_PORT -ErrorAction SilentlyContinue
if ($serverUp) {
    Write-Host "       ACM2 server started on port $ACM2_PORT" -ForegroundColor Green
    $cleared++
} else {
    Write-Host "       ACM2 server may still be starting..." -ForegroundColor DarkYellow
    $cleared++
}

# ----------------------------------------------------------------------------
# SUMMARY
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CACHE DESTRUCTION COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Cleared: $cleared cache types" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Failed:  $failed operations" -ForegroundColor Red
}
Write-Host ""
Write-Host "  Configuration:" -ForegroundColor White
Write-Host "    - ACM2 Root:  $ACM2_ROOT" -ForegroundColor White
Write-Host "    - Python:     $PYTHON_PATH" -ForegroundColor White
Write-Host "    - Port:       $ACM2_PORT" -ForegroundColor White
Write-Host ""
Write-Host "  Services restarted:" -ForegroundColor White
Write-Host "    - ACM2 Uvicorn (Python code reloaded)" -ForegroundColor White
Write-Host ""
Write-Host "  NEXT: Hard refresh browser (Ctrl+Shift+R)" -ForegroundColor Yellow
Write-Host ""
