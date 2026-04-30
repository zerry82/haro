param(
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "src\backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Backend venv python not found: $python"
}

Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*uvicorn*app.main*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

$args = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001")
if ($Reload) {
    Write-Warning "Uvicorn --reload can leave the port locked on Windows. Prefer stable mode unless you are actively debugging reload behavior."
    $args += "--reload"
}

Start-Process `
    -FilePath $python `
    -ArgumentList $args `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $backendDir "backend.dev.out.log") `
    -RedirectStandardError (Join-Path $backendDir "backend.dev.err.log")

Start-Sleep -Seconds 3

$health = Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/health" -UseBasicParsing -TimeoutSec 10
Write-Output $health.Content
