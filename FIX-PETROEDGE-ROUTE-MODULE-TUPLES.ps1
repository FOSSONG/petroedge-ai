$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$MainFile = Join-Path $ProjectRoot "backend\app\main.py"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupFile = "$MainFile.route-tuple-fix-$Timestamp.bak"

function Restore-And-Fail {
    param([string]$Message)
    Write-Host "`nERROR: $Message" -ForegroundColor Red
    if (Test-Path -LiteralPath $BackupFile) {
        Copy-Item -LiteralPath $BackupFile -Destination $MainFile -Force
        Write-Host "Original main.py restored from backup." -ForegroundColor Yellow
    }
    exit 1
}

Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath $MainFile)) {
    throw "Cannot find $MainFile"
}

Write-Host "[1/6] Backing up backend/app/main.py..." -ForegroundColor Cyan
Copy-Item -LiteralPath $MainFile -Destination $BackupFile -Force

$content = Get-Content -LiteralPath $MainFile -Raw

$oldLine = '    for module_name, prefix, tags, required in ROUTE_MODULES:'
$newBlock = @'
    for route_spec in ROUTE_MODULES:
        if len(route_spec) == 4:
            module_name, prefix, tags, required = route_spec
        elif len(route_spec) == 3:
            # Backward compatibility for legacy route declarations.
            module_name, prefix, tags = route_spec
            required = False
        else:
            raise ValueError(
                "Invalid ROUTE_MODULES entry. Expected "
                f"(module_name, prefix, tags[, required]), got: {route_spec!r}"
            )
'@

if ($content.Contains($newBlock.TrimEnd())) {
    Write-Host "[2/6] Compatibility correction is already present." -ForegroundColor Green
}
elseif ($content.Contains($oldLine)) {
    Write-Host "[2/6] Applying ROUTE_MODULES compatibility correction..." -ForegroundColor Cyan
    $content = $content.Replace($oldLine, $newBlock.TrimEnd())
    Set-Content -LiteralPath $MainFile -Value $content -Encoding utf8
}
else {
    Restore-And-Fail "Expected route-registration loop was not found. No unverified edit was applied."
}

$updated = Get-Content -LiteralPath $MainFile -Raw
foreach ($marker in @(
    'for route_spec in ROUTE_MODULES:',
    'if len(route_spec) == 4:',
    'elif len(route_spec) == 3:',
    'required = False'
)) {
    if (-not $updated.Contains($marker)) {
        Restore-And-Fail "Post-edit validation failed; missing marker: $marker"
    }
}

Write-Host "[3/6] Showing ROUTE_MODULES declarations for audit..." -ForegroundColor Cyan
Select-String -LiteralPath $MainFile -Pattern 'ROUTE_MODULES|for route_spec|len\(route_spec\)' -Context 0,3 |
    ForEach-Object { $_.ToString() } |
    Out-Host

Write-Host "[4/6] Rebuilding only the backend with Docker cache..." -ForegroundColor Cyan
docker compose build backend
if ($LASTEXITCODE -ne 0) {
    Restore-And-Fail "Backend image build failed."
}

Write-Host "[5/6] Recreating services without rebuilding the frontend..." -ForegroundColor Cyan
docker compose up -d --no-build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Compose did not fully start. Collecting backend logs..." -ForegroundColor Yellow
    docker compose logs --timestamps --tail 300 backend | Out-Host
    Restore-And-Fail "Backend failed after the correction."
}

Write-Host "[6/6] Waiting for backend health and reporting status..." -ForegroundColor Cyan
$healthy = $false
for ($i = 1; $i -le 18; $i++) {
    Start-Sleep -Seconds 5
    $status = docker inspect petroedge-mvp-backend --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>$null
    Write-Host "Attempt $i/18: $status"
    if ($status -match '^running healthy$') {
        $healthy = $true
        break
    }
    if ($status -match '^exited') {
        break
    }
}

docker compose ps -a | Out-Host

if (-not $healthy) {
    docker compose logs --timestamps --tail 300 backend | Out-Host
    Restore-And-Fail "Backend did not become healthy."
}

Write-Host "`nSUCCESS: Backend route registration is compatible with three- and four-field entries." -ForegroundColor Green
Write-Host "Backup retained at: $BackupFile" -ForegroundColor DarkGray
