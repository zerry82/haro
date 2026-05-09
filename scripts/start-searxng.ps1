param(
    [int]$Port = 8080,
    [string]$ContainerName = "haro-searxng",
    [string]$Image = "searxng/searxng:latest",
    [switch]$Required
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$settingsPath = Join-Path $PSScriptRoot "searxng-settings.yml"
$baseUrl = "http://127.0.0.1:$Port"

function Complete-Unavailable {
    param([string]$Message)

    if ($Required) {
        throw $Message
    }

    Write-Warning $Message
    exit 0
}

if (-not (Test-Path $settingsPath)) {
    Complete-Unavailable "SearXNG settings file not found: $settingsPath"
}

try {
    Get-Command docker -ErrorAction Stop | Out-Null
} catch {
    Complete-Unavailable "Docker CLI not found. Web search will be unavailable until SearXNG is started."
}

& docker info --format "{{.ServerVersion}}" *> $null
if ($LASTEXITCODE -ne 0) {
    Complete-Unavailable "Docker daemon is not available. Web search will be unavailable until SearXNG is started."
}

$containerOutput = & docker ps -a --filter "name=^/$ContainerName$" --format "{{.ID}}"
$containerId = ($containerOutput | Select-Object -First 1)
if ($containerId) {
    $containerId = $containerId.Trim()
}

if ($containerId) {
    $runningOutput = & docker inspect -f "{{.State.Running}}" $ContainerName
    $running = ($runningOutput | Select-Object -First 1)
    if ($running -and $running.Trim() -eq "true") {
        Write-Output $baseUrl
        exit 0
    }
}

if ($containerId) {
    Write-Host "Starting existing SearXNG container '$ContainerName'..."
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $dockerOutput = & docker start $ContainerName 2>&1
        $dockerExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        Complete-Unavailable "Failed to start SearXNG container '$ContainerName'."
    }
} else {
    Write-Host "Creating SearXNG container '$ContainerName' on $baseUrl..."
    $mountSpec = "type=bind,source=$settingsPath,target=/etc/searxng/settings.yml,readonly"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $dockerOutput = & docker run -d `
            --name $ContainerName `
            -p "127.0.0.1:${Port}:8080" `
            --mount $mountSpec `
            -e "SEARXNG_BASE_URL=$baseUrl/" `
            $Image 2>&1
        $dockerExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        if ($dockerOutput) {
            Write-Warning ($dockerOutput -join "`n")
        }
        Complete-Unavailable "Failed to create SearXNG container '$ContainerName'."
    }
}

for ($i = 0; $i -lt 20; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/search?q=haro&format=json" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            Write-Output $baseUrl
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

Write-Warning "SearXNG container is started, but the JSON endpoint is not ready yet: $baseUrl"
Write-Output $baseUrl
