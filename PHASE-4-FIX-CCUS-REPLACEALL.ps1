$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Panel = Join-Path $Root "frontend\src\features\platform\CcusWorkspacePanel.tsx"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root "patch-backups\phase4-ccus-replaceall-fix-$Stamp"
$Result = Join-Path $Root "PHASE-4-CCUS-REPLACEALL-FIX-RESULT.txt"

if (-not (Test-Path -LiteralPath $Panel -PathType Leaf)) {
    throw "CCUS panel not found: $Panel"
}

New-Item -ItemType Directory -Path $Backup -Force | Out-Null
Copy-Item -LiteralPath $Panel -Destination (Join-Path $Backup "CcusWorkspacePanel.tsx") -Force

$Content = [System.IO.File]::ReadAllText($Panel)

$Original = '.replaceAll("_"," ")'
$Replacement = '.replace(/_/g," ")'

if ($Content.Contains($Original)) {
    $Content = $Content.Replace($Original, $Replacement)
}
elseif ($Content.Contains($Replacement)) {
    Write-Host "Compatibility fix is already present." -ForegroundColor Yellow
}
else {
    throw "Expected replaceAll expression was not found in CcusWorkspacePanel.tsx"
}

[System.IO.File]::WriteAllText(
    $Panel,
    $Content,
    (New-Object System.Text.UTF8Encoding($false))
)

Set-Location $Root

Write-Host "[1/4] Checking for unsupported replaceAll calls..." -ForegroundColor Cyan
$Remaining = Get-ChildItem -LiteralPath (Join-Path $Root "frontend\src") -Recurse -File |
    Where-Object { $_.Extension -in @(".ts", ".tsx") } |
    Select-String -Pattern '\.replaceAll\('

if ($Remaining) {
    Write-Host "Other replaceAll calls exist:" -ForegroundColor Yellow
    foreach ($Match in $Remaining) {
        Write-Host "$($Match.Path):$($Match.LineNumber): $($Match.Line.Trim())"
    }
}

Write-Host "[2/4] Validating Compose..." -ForegroundColor Cyan
docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "[3/4] Rebuilding application..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate --remove-orphans
if ($LASTEXITCODE -ne 0) {
    throw "Docker rebuild failed. Backup: $Backup"
}

Write-Host "[4/4] Verifying health and CCUS routes..." -ForegroundColor Cyan
$Healthy = $false

for ($Attempt = 1; $Attempt -le 35; $Attempt++) {
    try {
        $Health = Invoke-RestMethod `
            -Uri "http://localhost:8000/health" `
            -Method Get `
            -TimeoutSec 10

        if ($Health.status -in @("ok", "healthy", "degraded")) {
            $Healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 4
    }
}

if (-not $Healthy) {
    docker compose ps -a
    docker compose logs backend --tail 250
    throw "Backend did not become healthy. Backup: $Backup"
}

$OpenApi = Invoke-RestMethod `
    -Uri "http://localhost:8000/openapi.json" `
    -Method Get `
    -TimeoutSec 30

$Paths = @($OpenApi.paths.PSObject.Properties.Name)
$Required = @(
    "/api/v1/ccus/capabilities",
    "/api/v1/ccus/screen",
    "/api/v1/ccus/runs",
    "/api/v1/ccus/runs/{run_id}"
)

$Missing = @($Required | Where-Object { $Paths -notcontains $_ })

@(
    "PETROEDGE AI PHASE 4 CCUS REPLACEALL FIX RESULT"
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
    "Backup: $Backup"
    "Missing CCUS paths: $($Missing.Count)"
    ""
    "$(docker compose ps -a | Out-String)"
) | Set-Content -LiteralPath $Result -Encoding utf8

if ($Missing.Count -gt 0) {
    throw "CCUS routes are missing. Review: $Result"
}

Write-Host ""
Write-Host "CCUS TYPESCRIPT COMPATIBILITY FIX COMPLETED" -ForegroundColor Green
Write-Host "Refresh the browser with Ctrl+F5 and open the CCUS tab." -ForegroundColor Yellow
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
