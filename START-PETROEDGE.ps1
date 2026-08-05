param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$FrontendUrl = "http://localhost:5173"
$ReadinessUrl = "http://localhost:8000/api/v1/readiness"
$Report = Join-Path $env:TEMP "PETROEDGE-START-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

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
    $LastError = ""
    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 8
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return
            }
        }
        catch {
            $LastError = $_.Exception.Message
        }
        Start-Sleep -Seconds 3
    }
    throw "Timed out waiting for $Uri. Last error: $LastError"
}

function Get-State {
    param([string]$Service)
    $Id = docker compose ps -q $Service
    if (-not $Id) {
        return "missing"
    }
    $State = docker inspect --format "{{.State.Status}}" $Id 2>$null
    if ($LASTEXITCODE -ne 0) {
        return "missing"
    }
    return $State
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

    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose configuration is invalid."
    }

    $BackendState = Get-State "backend"
    $FrontendState = Get-State "frontend"

    Log "Backend state: $BackendState"
    Log "Frontend state: $FrontendState"

    if ($BackendState -eq "running" -and $FrontendState -eq "running") {
        Log "Containers are already running." Cyan
    }
    elseif (
        $BackendState -in @("created", "exited") -or
        $FrontendState -in @("created", "exited")
    ) {
        Log "Starting existing containers." Cyan
        docker compose start backend frontend
        if ($LASTEXITCODE -ne 0) {
            throw "Existing containers could not be started."
        }
    }
    else {
        Log "Creating missing containers from local images." Cyan
        docker compose up -d --no-build --no-recreate backend frontend
        if ($LASTEXITCODE -ne 0) {
            throw "Containers could not be created from local images."
        }
    }

    Wait-Endpoint $ReadinessUrl 180
    Wait-Endpoint $FrontendUrl 120

    docker compose ps -a | Tee-Object -FilePath $Report -Append
    Log "PetroEdge started successfully." Green

    if (-not $NoBrowser) {
        Start-Process $FrontendUrl
    }
}
catch {
    Log "STARTUP FAILED: $($_.Exception.Message)" Red
    docker compose ps -a 2>&1 | Add-Content $Report
    docker compose logs --timestamps --tail 250 backend frontend 2>&1 |
        Add-Content $Report

    Write-Host "Diagnostic report: $Report" -ForegroundColor Yellow
    exit 1
}