param(
    [switch]$Reload,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "src\backend"
$venvDir = Join-Path $backendDir ".venv"
$python = Join-Path $backendDir ".venv\Scripts\python.exe"
$requirements = Join-Path $backendDir "requirements.txt"
$searxngScript = Join-Path $PSScriptRoot "start-searxng.ps1"

if (Test-Path $searxngScript) {
    $searxngBaseUrl = & $searxngScript | Select-Object -Last 1
    if ($searxngBaseUrl) {
        $env:WEB_SEARCH_PROVIDER = "searxng"
        $env:WEB_SEARCH_BASE_URL = $searxngBaseUrl
        Write-Host "Web search provider: searxng ($env:WEB_SEARCH_BASE_URL)"
    }
}

if (-not (Test-Path $python)) {
    python -m venv $venvDir
}

& $python -m pip install -r $requirements

$args = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", "8001")
if ($Reload) {
    $args += "--reload"
}

Push-Location $backendDir
try {
    & $python @args
} finally {
    Pop-Location
}
