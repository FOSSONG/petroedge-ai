$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\release-3-repair-$Stamp"

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    New-Item -ItemType Directory -Path (Split-Path $Path -Parent) -Force | Out-Null
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

function Backup-File {
    param([string]$Relative)
    $Source = Join-Path $ProjectRoot $Relative
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        $Destination = Join-Path $BackupRoot $Relative
        New-Item -ItemType Directory -Path (Split-Path $Destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
    }
}

function Restore-File {
    param([string]$Relative)
    $Target = Join-Path $ProjectRoot $Relative
    $Backup = Join-Path $BackupRoot $Relative
    if (Test-Path -LiteralPath $Backup -PathType Leaf) {
        New-Item -ItemType Directory -Path (Split-Path $Target -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $Backup -Destination $Target -Force
    }
}

function Wait-Http {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds = 180,
        [int]$IntervalSeconds = 3
    )
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $LastError = ""
    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 8
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) {
                return $Response.StatusCode
            }
        }
        catch {
            $LastError = $_.Exception.Message
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
    throw "Timed out waiting for $Uri. Last error: $LastError"
}

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}

Set-Location $ProjectRoot

$ManagedFiles = @(
    "backend\app\main.py",
    "backend\app\ml_lifecycle\__init__.py",
    "backend\app\ml_lifecycle\schemas.py",
    "backend\app\ml_lifecycle\service.py",
    "backend\app\api\routes\training_lifecycle.py",
    "backend\requirements-windows-dev.txt",
    "backend\pyproject.toml",
    "frontend\src\features\platform\platformApi.ts",
    "frontend\src\features\platform\TrainingWorkspacePanel.tsx",
    "frontend\src\features\platform\platformApi.release3.addition.ts"
)

Write-Host "[1/10] Validating project and current containers..." -ForegroundColor Cyan
foreach ($Required in @(
    "docker-compose.yml",
    "backend\app\main.py",
    "frontend\src\features\platform\platformApi.ts",
    "frontend\src\features\platform\TrainingWorkspacePanel.tsx"
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $Required))) {
        throw "Required project file missing: $Required"
    }
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration is invalid." }

Write-Host "[2/10] Creating timestamped backup..." -ForegroundColor Cyan
foreach ($Relative in $ManagedFiles) { Backup-File $Relative }

try {
    Write-Host "[3/10] Removing stale Release 3 build fragments..." -ForegroundColor Cyan
    $StaleFragment = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.release3.addition.ts"
    if (Test-Path -LiteralPath $StaleFragment) {
        Remove-Item -LiteralPath $StaleFragment -Force
    }

    Write-Host "[4/10] Validating installed Release 3 source..." -ForegroundColor Cyan
    foreach ($RequiredRelease3 in @(
        "backend\app\ml_lifecycle\schemas.py",
        "backend\app\ml_lifecycle\service.py",
        "backend\app\api\routes\training_lifecycle.py",
        "frontend\src\features\platform\TrainingWorkspacePanel.tsx"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $RequiredRelease3))) {
            throw "Release 3 source is missing: $RequiredRelease3. Extract the full Release 3 package into a separate folder and run its installer first."
        }
    }

    Write-Host "[5/10] Repairing lifecycle API registration..." -ForegroundColor Cyan
    $MainPath = Join-Path $ProjectRoot "backend\app\main.py"
    $Main = [IO.File]::ReadAllText($MainPath)
    $RouteLine = '    ("training_lifecycle", "/training-lifecycle", ("Model Training and Lifecycle",), True),'
    if (-not $Main.Contains($RouteLine)) {
        $Anchor = '    ("models", "/models", ("Models",), True),'
        if (-not $Main.Contains($Anchor)) { throw "Could not find the models route anchor in backend\app\main.py." }
        $Main = $Main.Replace($Anchor, $Anchor + "`r`n" + $RouteLine)
        Write-Utf8NoBom -Path $MainPath -Content $Main
    }

    Write-Host "[6/10] Repairing frontend lifecycle API integration..." -ForegroundColor Cyan
    $ApiPath = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts"
    $Api = [IO.File]::ReadAllText($ApiPath)
    if ($Api -notmatch "fetchLifecycleAlgorithms") {
        throw "Release 3 API functions are not present in platformApi.ts. Use the full corrected Release 3 package rather than this repair-only package."
    }

    Write-Host "[7/10] Checking Python source and dependencies..." -ForegroundColor Cyan
    docker compose run --rm --no-deps backend python -m compileall -q /app/app
    if ($LASTEXITCODE -ne 0) { throw "Backend Python compilation failed." }

    Write-Host "[8/10] Rebuilding backend and frontend..." -ForegroundColor Cyan
    docker compose build backend frontend
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }

    Write-Host "[9/10] Recreating services without fixed sleeps..." -ForegroundColor Cyan
    docker compose up -d --no-build backend frontend
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose could not recreate the services." }

    Write-Host "Waiting for backend health..." -ForegroundColor DarkCyan
    $BackendStatus = Wait-Http -Uri "http://localhost:8000/health" -TimeoutSeconds 180 -IntervalSeconds 3
    Write-Host "Backend responded with HTTP $BackendStatus." -ForegroundColor Green

    Write-Host "Waiting for frontend..." -ForegroundColor DarkCyan
    $FrontendStatus = Wait-Http -Uri "http://localhost:3000" -TimeoutSeconds 120 -IntervalSeconds 3
    Write-Host "Frontend responded with HTTP $FrontendStatus." -ForegroundColor Green

    Write-Host "[10/10] Verifying Release 3 routes and runtime status..." -ForegroundColor Cyan
    $OpenApi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 20
    foreach ($Route in @(
        "/api/v1/training-lifecycle/algorithms",
        "/api/v1/training-lifecycle/train",
        "/api/v1/training-lifecycle/registry",
        "/api/v1/training-lifecycle/predict"
    )) {
        if (-not $OpenApi.paths.PSObject.Properties.Name.Contains($Route)) {
            throw "Required Release 3 route is missing: $Route"
        }
    }

    docker compose ps -a
    Write-Host ""
    Write-Host "SUCCESS: Release 3 repair completed." -ForegroundColor Green
    Write-Host "The installer waited on actual HTTP readiness rather than a fixed startup delay." -ForegroundColor Green
    Write-Host "Backup: $BackupRoot" -ForegroundColor DarkGray
}
catch {
    $Failure = $_.Exception.Message
    Write-Host ""
    Write-Host "RELEASE 3 REPAIR FAILED: $Failure" -ForegroundColor Red

    Write-Host "Collecting diagnostics..." -ForegroundColor Yellow
    docker compose ps -a | Out-Host
    docker compose logs --tail 160 backend frontend | Out-Host

    Write-Host "Restoring backed-up source..." -ForegroundColor Yellow
    foreach ($Relative in $ManagedFiles) {
        if ($Relative -ne "frontend\src\features\platform\platformApi.release3.addition.ts") {
            Restore-File $Relative
        }
    }

    # Never restore the invalid standalone TypeScript fragment.
    $StaleFragment = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.release3.addition.ts"
    if (Test-Path -LiteralPath $StaleFragment) {
        Remove-Item -LiteralPath $StaleFragment -Force
    }

    Write-Host "Restoring last buildable containers..." -ForegroundColor Yellow
    docker compose build backend frontend | Out-Host
    if ($LASTEXITCODE -eq 0) {
        docker compose up -d --no-build backend frontend | Out-Host
    }
    exit 1
}
