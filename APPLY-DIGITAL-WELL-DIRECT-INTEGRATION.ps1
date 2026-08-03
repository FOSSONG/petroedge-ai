$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$RelativeTarget = "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Target = Join-Path $ProjectRoot $RelativeTarget
$Replacement = Join-Path $PSScriptRoot $RelativeTarget
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\digital-well-direct-integration-$Stamp"
$Backup = Join-Path $BackupRoot $RelativeTarget

function Restore-PreviousVersion {
    if (Test-Path -LiteralPath $Backup) {
        Copy-Item -LiteralPath $Backup -Destination $Target -Force
        Write-Host "Previous Digital Well Twin source restored." -ForegroundColor Yellow
    }
}

if (-not (Test-Path -LiteralPath $Target)) {
    throw "Target file not found: $Target"
}
if (-not (Test-Path -LiteralPath $Replacement)) {
    throw "Replacement file not found: $Replacement"
}

Set-Location $ProjectRoot

Write-Host "[1/7] Validating the installed Digital Well Twin..." -ForegroundColor Cyan
$current = [IO.File]::ReadAllText($Target)
foreach ($marker in @(
    "Digital Well Twin",
    "Dynamic 3D wellbore and depth-property envelope",
    "fetchDatasets",
    "fetchAssets",
    "fetchReplay"
)) {
    if (-not $current.Contains($marker)) {
        throw "Unexpected installed source. Missing marker: $marker"
    }
}

Write-Host "[2/7] Creating timestamped backup..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path (Split-Path $Backup -Parent) -Force | Out-Null
Copy-Item -LiteralPath $Target -Destination $Backup -Force

try {
    Write-Host "[3/7] Installing direct Dataset and Asset integration..." -ForegroundColor Cyan
    Copy-Item -LiteralPath $Replacement -Destination $Target -Force

    $installed = [IO.File]::ReadAllText($Target)
    foreach ($required in @(
        "Well dataset",
        "Registered well asset",
        "Datasets and Assets are the platform source of truth",
        "Optional persisted engineering state"
    )) {
        if (-not $installed.Contains($required)) {
            throw "Replacement validation failed. Missing marker: $required"
        }
    }
    foreach ($removed in @(
        "Create well twin",
        "Create Digital Well Twin",
        "Create persistent twin"
    )) {
        if ($installed.Contains($removed)) {
            throw "Obsolete creation workflow remains: $removed"
        }
    }

    Write-Host "[4/7] Validating Docker Compose..." -ForegroundColor Cyan
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed." }

    Write-Host "[5/7] Building only the frontend image..." -ForegroundColor Cyan
    docker compose build frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

    Write-Host "[6/7] Recreating the frontend without rebuilding the backend..." -ForegroundColor Cyan
    docker compose up -d --no-build frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend recreation failed." }

    Write-Host "[7/7] Verifying service state..." -ForegroundColor Cyan
    Start-Sleep -Seconds 8
    docker compose ps -a | Out-Host

    $frontendState = docker inspect petroedge-mvp-frontend --format '{{.State.Status}}' 2>$null
    if ($frontendState -ne "running") {
        throw "Frontend container is not running. State: $frontendState"
    }

    Write-Host "`nSUCCESS: Digital Well Twin now loads directly from Datasets and Assets." -ForegroundColor Green
    Write-Host "Backup: $Backup" -ForegroundColor DarkGray
}
catch {
    Write-Host "`nINSTALLATION FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Restore-PreviousVersion

    Write-Host "Rebuilding the previous frontend source..." -ForegroundColor Yellow
    docker compose build frontend | Out-Host
    docker compose up -d --no-build frontend | Out-Host
    exit 1
}
