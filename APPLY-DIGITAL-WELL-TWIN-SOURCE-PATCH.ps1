$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $ScriptRoot "src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Target = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root "patch-backups\digital-well-twin-source-$Stamp"
$Report = Join-Path $Root "DIGITAL-WELL-TWIN-SOURCE-PATCH-RESULT.txt"

if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "Patch source file not found: $Source"
}
if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
    throw "PetroEdge target file not found: $Target"
}

New-Item -ItemType Directory -Path $Backup -Force | Out-Null
Copy-Item -LiteralPath $Target -Destination (Join-Path $Backup "ReservoirDigitalTwinPanel.tsx") -Force

try {
    Write-Host "[1/5] Installing source-level Digital Well Twin panel..." -ForegroundColor Cyan
    Copy-Item -LiteralPath $Source -Destination $Target -Force

    $Installed = [IO.File]::ReadAllText($Target)
    foreach ($Marker in @(
        "Create Digital Well Twin",
        "Dynamic 3D wellbore and depth-property envelope",
        'component="form"',
        "fetchReplay"
    )) {
        if (-not $Installed.Contains($Marker)) {
            throw "Installed source validation failed. Missing marker: $Marker"
        }
    }

    Write-Host "[2/5] Validating Docker Compose..." -ForegroundColor Cyan
    Set-Location $Root
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed." }

    Write-Host "[3/5] Building the real frontend source..." -ForegroundColor Cyan
    $env:BUILDKIT_PROGRESS = "plain"
    docker compose --progress plain build frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend compilation failed." }

    Write-Host "[4/5] Recreating frontend container..." -ForegroundColor Cyan
    docker compose up -d --force-recreate frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend container recreation failed." }

    Write-Host "[5/5] Verifying compiled Digital Well Twin markers..." -ForegroundColor Cyan
    $MarkerOutput = docker compose exec -T frontend sh -lc "grep -R -l 'Dynamic 3D wellbore and depth-property envelope' /usr/share/nginx/html/assets 2>/dev/null || true" 2>&1
    if (-not (($MarkerOutput -join "`n") -match "ReservoirDigitalTwinPanel")) {
        throw "Compiled Digital Well Twin marker was not found in the frontend assets."
    }

    @(
        "PETROEDGE AI DIGITAL WELL TWIN SOURCE PATCH",
        "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
        "Status: SUCCESS",
        "Backup: $Backup",
        "Target: $Target",
        "",
        "Compiled marker:",
        $MarkerOutput,
        "",
        (docker compose ps -a | Out-String)
    ) | Set-Content -LiteralPath $Report -Encoding utf8

    Write-Host "" 
    Write-Host "DIGITAL WELL TWIN SOURCE PATCH COMPLETED" -ForegroundColor Green
    Write-Host "Result: $Report"
    Write-Host "Backup: $Backup"
    Write-Host "Close all PetroEdge tabs, reopen http://localhost:5173, then press Ctrl+Shift+R once." -ForegroundColor Yellow
}
catch {
    Write-Host "Patch failed. Restoring the original panel..." -ForegroundColor Red
    Copy-Item -LiteralPath (Join-Path $Backup "ReservoirDigitalTwinPanel.tsx") -Destination $Target -Force
    @(
        "PETROEDGE AI DIGITAL WELL TWIN SOURCE PATCH",
        "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
        "Status: FAILED AND ROLLED BACK",
        "Backup: $Backup",
        "Error: $($_.Exception.Message)"
    ) | Set-Content -LiteralPath $Report -Encoding utf8
    throw
}
