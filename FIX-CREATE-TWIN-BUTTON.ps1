$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Target = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Source = Join-Path $PSScriptRoot "src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = "$Target.create-button-$Stamp.bak"

function Restore-And-Fail {
    param([string]$Message)

    Write-Host "`nERROR: $Message" -ForegroundColor Red

    if (Test-Path -LiteralPath $Backup) {
        Copy-Item -LiteralPath $Backup -Destination $Target -Force
        Write-Host "Original Digital Twin panel restored." -ForegroundColor Yellow
    }

    exit 1
}

if (-not (Test-Path -LiteralPath $Target)) {
    throw "Target component was not found: $Target"
}

if (-not (Test-Path -LiteralPath $Source)) {
    throw "Corrected component was not found beside this installer."
}

Set-Location $Root

Write-Host "[1/6] Validating the existing Digital Twin source..." -ForegroundColor Cyan
$current = [IO.File]::ReadAllText($Target)

foreach ($marker in @(
    "Create Digital Well Twin",
    "Dynamic 3D wellbore and depth-property envelope",
    "fetchReplay",
    'component="form"'
)) {
    if (-not $current.Contains($marker)) {
        throw "The installed panel is not the expected Digital Well Twin version. Missing marker: $marker"
    }
}

Write-Host "[2/6] Creating a timestamped backup..." -ForegroundColor Cyan
Copy-Item -LiteralPath $Target -Destination $Backup -Force

try {
    Write-Host "[3/6] Installing the Create Twin interaction correction..." -ForegroundColor Cyan
    Copy-Item -LiteralPath $Source -Destination $Target -Force

    $installed = [IO.File]::ReadAllText($Target)
    foreach ($marker in @(
        "createValidationError",
        "openCreateDialog",
        "disabled={create.isPending}",
        "create the twin manually and link a dataset later"
    )) {
        if (-not $installed.Contains($marker)) {
            throw "Installed source validation failed. Missing marker: $marker"
        }
    }

    Write-Host "[4/6] Validating Docker Compose..." -ForegroundColor Cyan
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose configuration validation failed."
    }

    Write-Host "[5/6] Building only the frontend..." -ForegroundColor Cyan
    docker compose build frontend
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend compilation failed."
    }

    Write-Host "[6/6] Recreating the frontend from the corrected image..." -ForegroundColor Cyan
    docker compose up -d --no-build frontend
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend recreation failed."
    }

    Start-Sleep -Seconds 5
    docker compose ps -a | Out-Host

    Write-Host "`nSUCCESS: Create Twin is now actionable and validates visibly." -ForegroundColor Green
    Write-Host "Backup retained at: $Backup" -ForegroundColor DarkGray
}
catch {
    Copy-Item -LiteralPath $Backup -Destination $Target -Force
    Write-Host "`nThe corrected source could not be validated. Restoring and rebuilding the previous frontend..." -ForegroundColor Yellow
    docker compose build frontend | Out-Host
    docker compose up -d --no-build frontend | Out-Host
    Restore-And-Fail $_.Exception.Message
}
