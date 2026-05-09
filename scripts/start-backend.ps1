param(
    [switch]$Reload,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "src\backend"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$searxngScript = Join-Path $PSScriptRoot "start-searxng.ps1"

if (-not (Test-Path $python)) {
    throw "Backend venv python not found: $python"
}

if (Test-Path $searxngScript) {
    $searxngBaseUrl = & $searxngScript | Select-Object -Last 1
    if ($searxngBaseUrl) {
        $env:WEB_SEARCH_PROVIDER = "searxng"
        $env:WEB_SEARCH_BASE_URL = $searxngBaseUrl
        Write-Output "Web search provider: searxng ($env:WEB_SEARCH_BASE_URL)"
    }
}

Get-CimInstance Win32_Process |
    Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*uvicorn*app.main*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

$args = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", "8001")
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
