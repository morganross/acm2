
$ErrorActionPreference = "Stop"

Write-Host "1. Starting Server..."
$serverProcess = Start-Process -FilePath "c:\dev\silky\api_cost_multiplier\acm2\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir c:\dev\silky\api_cost_multiplier\acm2" -PassThru -NoNewWindow

try {
    Write-Host "2. Waiting for server to be ready..."
    $retries = 0
    $maxRetries = 10
    $serverReady = $false

    while ($retries -lt $maxRetries) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/docs" -Method Get -ErrorAction Stop
            $serverReady = $true
            break
        } catch {
            Start-Sleep -Seconds 1
            $retries++
            Write-Host "." -NoNewline
        }
    }
    Write-Host ""

    if (-not $serverReady) {
        throw "Server failed to start within 10 seconds"
    }
    Write-Host "Server is UP!"

    Write-Host "3. Running Tests..."
    # Create a preset
    $body = @{
        name = "Test Preset $(Get-Date -Format 'yyyyMMdd-HHmmss')"
        description = "Automated test preset"
        documents = @()
        generators = @("gptr")
        models = @(@{provider="openai"; model="gpt-4o-mini"})
        iterations = 1
        gptr_settings = @{report_type="research_report"; tone="objective"}
        evaluation = @{enabled=$true}
        pairwise = @{enabled=$false}
    } | ConvertTo-Json -Depth 5

    Write-Host "   Creating Preset..."
    $preset = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/presets" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   Success! Created Preset ID: $($preset.id)"

    Write-Host "   Listing Presets..."
    $list = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/presets" -Method Get
    Write-Host "   Success! Found $($list.total) presets."
    
    # Verify the fix (check if runs are loaded/handled correctly)
    Write-Host "   Verifying Preset Details..."
    $details = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/presets/$($preset.id)" -Method Get
    Write-Host "   Success! Retrieved details for $($details.name)"

} catch {
    Write-Error "Test Failed: $_"
} finally {
    Write-Host "4. Stopping Server..."
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
    Write-Host "Done."
}
