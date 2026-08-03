$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\release-3-model-lifecycle-$Stamp"

$Files = @(
  "backend\app\ml_lifecycle\__init__.py",
  "backend\app\ml_lifecycle\schemas.py",
  "backend\app\ml_lifecycle\service.py",
  "backend\app\api\routes\training_lifecycle.py",
  "frontend\src\features\platform\TrainingWorkspacePanel.tsx"
)

function Restore-Release3 {
  foreach ($Relative in $Files) {
    $Target = Join-Path $ProjectRoot $Relative
    $Backup = Join-Path $BackupRoot $Relative
    if (Test-Path -LiteralPath $Backup) {
      New-Item -ItemType Directory -Path (Split-Path $Target -Parent) -Force | Out-Null
      Copy-Item -LiteralPath $Backup -Destination $Target -Force
    } elseif (Test-Path -LiteralPath $Target) {
      Remove-Item -LiteralPath $Target -Force
    }
  }
  foreach ($Relative in @("backend\app\main.py","frontend\src\features\platform\platformApi.ts","backend\pyproject.toml","backend\requirements-windows-dev.txt")) {
    $Backup = Join-Path $BackupRoot $Relative
    if (Test-Path -LiteralPath $Backup) {
      Copy-Item -LiteralPath $Backup -Destination (Join-Path $ProjectRoot $Relative) -Force
    }
  }
}

if (-not (Test-Path -LiteralPath $ProjectRoot)) { throw "Project not found: $ProjectRoot" }
Set-Location $ProjectRoot

Write-Host "[1/9] Validating current source..." -ForegroundColor Cyan
foreach ($Required in @("backend\app\main.py","frontend\src\features\platform\platformApi.ts","frontend\src\features\platform\TrainingWorkspacePanel.tsx")) {
  if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $Required))) { throw "Required source missing: $Required" }
}

Write-Host "[2/9] Creating transactional backup..." -ForegroundColor Cyan
foreach ($Relative in @($Files + @("backend\app\main.py","frontend\src\features\platform\platformApi.ts","backend\pyproject.toml","backend\requirements-windows-dev.txt"))) {
  $Target = Join-Path $ProjectRoot $Relative
  if (Test-Path -LiteralPath $Target) {
    $Backup = Join-Path $BackupRoot $Relative
    New-Item -ItemType Directory -Path (Split-Path $Backup -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $Target -Destination $Backup -Force
  }
}

try {
  Write-Host "[3/9] Installing Release 3 modules..." -ForegroundColor Cyan
  foreach ($Relative in $Files) {
    $Source = Join-Path $PSScriptRoot $Relative
    $Target = Join-Path $ProjectRoot $Relative
    New-Item -ItemType Directory -Path (Split-Path $Target -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
  }

  # Remove the obsolete standalone TypeScript fragment from the first package.
  # Its contents belong inside platformApi.ts and must not be compiled separately.
  $StrayApiFragment = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.release3.addition.ts"
  if (Test-Path -LiteralPath $StrayApiFragment) {
    Remove-Item -LiteralPath $StrayApiFragment -Force
  }

  Write-Host "[4/9] Registering lifecycle API route..." -ForegroundColor Cyan
  $MainPath = Join-Path $ProjectRoot "backend\app\main.py"
  $Main = [IO.File]::ReadAllText($MainPath)
  if (-not $Main.Contains('("training_lifecycle", "/training-lifecycle"')) {
    $Anchor = '    ("models", "/models", ("Models",), True),'
    if (-not $Main.Contains($Anchor)) { throw "Could not locate models route anchor." }
    $Main = $Main.Replace($Anchor, $Anchor + "`r`n" + '    ("training_lifecycle", "/training-lifecycle", ("Model Training and Lifecycle",), True),')
    [IO.File]::WriteAllText($MainPath,$Main,[Text.UTF8Encoding]::new($false))
  }

  Write-Host "[5/9] Extending frontend API..." -ForegroundColor Cyan
  $ApiPath = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts"
  $Api = [IO.File]::ReadAllText($ApiPath)
  if (-not $Api.Contains("fetchLifecycleAlgorithms")) {
    $Addition = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "frontend\src\features\platform\platformApi.release3.addition.txt"))
    $Api = $Api.TrimEnd() + "`r`n`r`n" + $Addition + "`r`n"
    [IO.File]::WriteAllText($ApiPath,$Api,[Text.UTF8Encoding]::new($false))
  }

  Write-Host "[6/9] Ensuring CPU model dependencies..." -ForegroundColor Cyan
  $Req = Join-Path $ProjectRoot "backend\requirements-windows-dev.txt"
  if (Test-Path $Req) {
    $Content = [IO.File]::ReadAllText($Req)
    foreach ($Line in @("scikit-learn>=1.5,<2","xgboost>=2.1,<4","joblib>=1.4,<2")) {
      $Name = $Line.Split(">")[0]
      if ($Content -notmatch "(?im)^$([regex]::Escape($Name))") { $Content = $Content.TrimEnd() + "`r`n" + $Line }
    }
    [IO.File]::WriteAllText($Req,$Content+"`r`n",[Text.UTF8Encoding]::new($false))
  }

  $Pyproject = Join-Path $ProjectRoot "backend\pyproject.toml"
  if (Test-Path $Pyproject) {
    $Content = [IO.File]::ReadAllText($Pyproject)
    if ($Content -notmatch 'xgboost') {
      $Anchor = '"scikit-learn'
      $Index = $Content.IndexOf($Anchor)
      if ($Index -ge 0) {
        $LineEnd = $Content.IndexOf("`n",$Index)
        $Content = $Content.Insert($LineEnd+1,'  "xgboost>=2.1,<4",'+"`n")
      }
      [IO.File]::WriteAllText($Pyproject,$Content,[Text.UTF8Encoding]::new($false))
    }
  }

  Write-Host "[7/9] Validating Python imports and Compose..." -ForegroundColor Cyan
  docker compose config --quiet
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose validation failed." }

  Write-Host "[8/9] Building affected services..." -ForegroundColor Cyan
  docker compose build backend frontend
  if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }
  docker compose up -d --no-build backend frontend
  if ($LASTEXITCODE -ne 0) { throw "Service recreation failed." }
  Start-Sleep -Seconds 12

  Write-Host "[9/9] Verifying Release 3 endpoints..." -ForegroundColor Cyan
  $Health = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8000/health" -TimeoutSec 20
  if ($Health.StatusCode -ne 200) { throw "Backend health check failed." }

  $OpenApi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 20
  foreach ($Route in @(
    "/api/v1/training-lifecycle/algorithms",
    "/api/v1/training-lifecycle/train",
    "/api/v1/training-lifecycle/registry",
    "/api/v1/training-lifecycle/predict"
  )) {
    if (-not $OpenApi.paths.PSObject.Properties.Name.Contains($Route)) { throw "Missing Release 3 route: $Route" }
  }

  Write-Host "`nSUCCESS: PetroEdge AI Release 3 Model Training and Lifecycle is installed." -ForegroundColor Green
  Write-Host "Backup: $BackupRoot" -ForegroundColor DarkGray
}
catch {
  Write-Host "`nRELEASE 3 INSTALLATION FAILED: $($_.Exception.Message)" -ForegroundColor Red
  Restore-Release3
  docker compose build backend frontend | Out-Host
  docker compose up -d --no-build backend frontend | Out-Host
  exit 1
}
