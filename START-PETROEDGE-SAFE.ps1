param(
    [ValidateSet("Offline", "Online")]
    [string]$Mode = "Offline"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$FrontendUrl = "http://localhost:5173"
$ReadinessUrl = "http://localhost:8000/api/v1/readiness"
$Report = Join-Path $env:TEMP "PETROEDGE-STARTUP-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"

function Write-StartupLog {
    param(
        [string]$Message,
        [ConsoleColor]$Colour = [ConsoleColor]::Gray
    )

    $Line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $Line -ForegroundColor $Colour
    Add-Content -LiteralPath $Report -Value $Line -Encoding utf8
}

function Test-WebEndpoint {
    param([string]$Uri)

    try {
        $Response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri $Uri `
            -TimeoutSec 5

        return $Response.StatusCode -ge 200 -and
            $Response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-WebEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $LastError = ""

    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest `
                -UseBasicParsing `
                -Uri $Uri `
                -TimeoutSec 8

            if (
                $Response.StatusCode -ge 200 -and
                $Response.StatusCode -lt 500
            ) {
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

function Get-MissingComposeImages {
    $Images = @(docker compose config --images | Sort-Object -Unique)
    $Missing = @()

    foreach ($Image in $Images) {
        docker image inspect $Image *> $null

        if ($LASTEXITCODE -ne 0) {
            $Missing += $Image
        }
    }

    return @($Missing)
}

function Save-Diagnostics {
    "`n=== DOCKER VERSION ===" | Add-Content $Report
    docker version 2>&1 | Add-Content $Report

    "`n=== CONTAINERS ===" | Add-Content $Report
    docker compose ps -a 2>&1 | Add-Content $Report

    "`n=== MIGRATION LOGS ===" | Add-Content $Report
    docker compose logs --timestamps --tail 150 migrate 2>&1 |
        Add-Content $Report

    "`n=== BACKEND LOGS ===" | Add-Content $Report
    docker compose logs --timestamps --tail 250 backend 2>&1 |
        Add-Content $Report

    "`n=== FRONTEND LOGS ===" | Add-Content $Report
    docker compose logs --timestamps --tail 150 frontend 2>&1 |
        Add-Content $Report
}

"PETROEDGE AI SAFE STARTUP" |
    Set-Content -LiteralPath $Report -Encoding utf8

try {
    Set-Location $ProjectRoot

    Write-StartupLog "Mode: $Mode" Cyan

    if (Test-WebEndpoint $FrontendUrl) {
        Write-StartupLog "PetroEdge is already running." Green
        Start-Process $FrontendUrl
        exit 0
    }

    Write-StartupLog "Checking Docker Desktop." Cyan
    docker version | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Desktop is not ready. Start Docker Desktop and wait for Engine running."
    }

    Write-StartupLog "Validating Docker Compose." Cyan
    docker compose config --quiet

    if ($LASTEXITCODE -ne 0) {
        throw "The PetroEdge Docker Compose configuration is invalid."
    }

    $MissingImages = @(Get-MissingComposeImages)

    if ($MissingImages.Count -gt 0) {
        if ($Mode -eq "Offline") {
            throw "Offline startup cannot continue because local images are missing: $($MissingImages -join ', '). Use the online launcher once."
        }

        Write-StartupLog "Required images are missing. Building online." Yellow

        docker compose build migrate backend frontend

        if ($LASTEXITCODE -ne 0) {
            throw "Online build failed. Confirm internet access to Docker Hub."
        }
    }
    else {
        Write-StartupLog "All required images exist locally. Skipping build." Green
    }

    Write-StartupLog "Starting PetroEdge from local images." Cyan

    docker compose up -d --no-build

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose could not start PetroEdge."
    }

    Write-StartupLog "Waiting for backend readiness." Cyan
    Wait-WebEndpoint -Uri $ReadinessUrl -TimeoutSeconds 180

    Write-StartupLog "Waiting for frontend." Cyan
    Wait-WebEndpoint -Uri $FrontendUrl -TimeoutSeconds 120

    docker compose ps -a |
        Tee-Object -FilePath $Report -Append

    Write-StartupLog "PetroEdge started successfully." Green
    Write-StartupLog "Opening $FrontendUrl" Green

    Start-Process $FrontendUrl
}
catch {
    Write-StartupLog "STARTUP FAILED: $($_.Exception.Message)" Red

    try {
        Set-Location $ProjectRoot
        Save-Diagnostics
    }
    catch {
    }

    Write-Host ""
    Write-Host "Diagnostic report:" -ForegroundColor Yellow
    Write-Host $Report -ForegroundColor Yellow
    exit 1
}