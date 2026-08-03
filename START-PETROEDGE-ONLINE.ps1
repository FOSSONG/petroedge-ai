$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Report = Join-Path $env:TEMP "PETROEDGE-ONLINE-STARTUP-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
Set-Location $ProjectRoot

function Log([string]$Message) {
    $Line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $Line
    Add-Content -LiteralPath $Report -Value $Line -Encoding utf8
}

function Wait-Url([string]$Uri, [int]$TimeoutSeconds) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 8
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return
            }
        } catch {}
        Start-Sleep -Seconds 3
    }
    throw "Timed out waiting for $Uri"
}

try {
    Log "Checking Docker Desktop."
    docker version | Out-Null

    Log "Validating Compose."
    docker compose config --quiet

    Log "Building current Release 4.5 images."
    docker compose build migrate backend frontend
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }

    Log "Stopping only this Compose project."
    docker compose down --remove-orphans --timeout 15

    Log "Starting migration, backend and frontend."
    docker compose up -d --no-build
    if ($LASTEXITCODE -ne 0) { throw "Docker startup failed." }

    Log "Waiting for backend readiness."
    Wait-Url "http://localhost:8000/api/v1/readiness" 180

    Log "Waiting for frontend."
    Wait-Url "http://localhost:5173/" 120

    docker compose ps -a | Tee-Object -FilePath $Report -Append
    Log "PetroEdge AI online startup completed."
    Start-Process "http://localhost:5173"
}
catch {
    Log "ONLINE STARTUP FAILED: $($_.Exception.Message)"
    docker compose ps -a | Tee-Object -FilePath $Report -Append
    docker compose logs --timestamps --tail 250 migrate backend frontend |
        Tee-Object -FilePath $Report -Append
    Write-Host "Diagnostic report: $Report" -ForegroundColor Yellow
    exit 1
}