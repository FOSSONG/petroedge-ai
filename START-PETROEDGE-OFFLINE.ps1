param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$FrontendUrl = "http://localhost:5173"
$ReadinessUrl = "http://localhost:8000/api/v1/readiness"
$ComposeFiles = @(
    "-f", (Join-Path $ProjectRoot "docker-compose.yml"),
    "-f", (Join-Path $ProjectRoot "compose.offline.yml")
)
$Report = Join-Path $env:TEMP "PETROEDGE-OFFLINE-START-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

function Log {
    param([string]$Message, [ConsoleColor]$Colour = [ConsoleColor]::Gray)
    $Line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $Line -ForegroundColor $Colour
    Add-Content -LiteralPath $Report -Value $Line -Encoding utf8
}

function Test-Endpoint {
    param([string]$Uri)
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
        return $Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-Endpoint {
    param([string]$Uri, [int]$TimeoutSeconds)
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        if (Test-Endpoint $Uri) {
            return
        }
        Start-Sleep -Seconds 3
    }
    throw "Timed out waiting for $Uri"
}

try {
    Set-Location $ProjectRoot

    if (Test-Endpoint $FrontendUrl) {
        Log "PetroEdge is already running." Green
        if (-not $NoBrowser) {
            Start-Process $FrontendUrl
        }
        exit 0
    }

    docker info *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop is not ready."
    }

    foreach ($Image in @(
        "petroedge-release45-backend",
        "petroedge-release45-frontend"
    )) {
        docker image inspect $Image *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Required local image is missing: $Image"
        }
    }

    Log "Starting PetroEdge in strict offline mode." Cyan

    docker compose @ComposeFiles up `
        -d `
        --no-build `
        --no-recreate `
        --pull never `
        backend `
        frontend

    if ($LASTEXITCODE -ne 0) {
        throw "Offline startup failed."
    }

    Wait-Endpoint $ReadinessUrl 180
    Wait-Endpoint $FrontendUrl 120

    docker compose @ComposeFiles ps -a |
        Tee-Object -FilePath $Report -Append

    Log "PetroEdge offline runtime is ready." Green

    if (-not $NoBrowser) {
        Start-Process $FrontendUrl
    }
}
catch {
    Log "OFFLINE START FAILED: $($_.Exception.Message)" Red
    docker compose @ComposeFiles ps -a 2>&1 | Add-Content $Report
    docker compose @ComposeFiles logs --timestamps --tail 200 backend frontend 2>&1 |
        Add-Content $Report

    Write-Host "Diagnostic report: $Report" -ForegroundColor Yellow
    exit 1
}