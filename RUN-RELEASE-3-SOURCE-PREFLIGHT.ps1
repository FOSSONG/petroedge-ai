$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutputRoot = Join-Path $ProjectRoot "release3-preflight-$Stamp"
$Bundle = Join-Path $ProjectRoot "PETROEDGE-RELEASE-3-SOURCE-BUNDLE-$Stamp.zip"
$Report = Join-Path $OutputRoot "RELEASE-3-PREFLIGHT-REPORT.txt"

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

function Add-Section {
    param([string]$Title)
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ""
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ("=" * 110)
    Add-Content -LiteralPath $Report -Encoding utf8 -Value $Title
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ("=" * 110)
}

function Copy-RelativeFile {
    param([string]$RelativePath)
    $Source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { return }
    $Destination = Join-Path $OutputRoot $RelativePath
    New-Item -ItemType Directory -Path (Split-Path $Destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

"PETROEDGE AI RELEASE 3 SOURCE PREFLIGHT" | Set-Content -LiteralPath $Report -Encoding utf8
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')" | Add-Content -LiteralPath $Report -Encoding utf8
"Project: $ProjectRoot" | Add-Content -LiteralPath $Report -Encoding utf8

Set-Location $ProjectRoot

Add-Section "DOCKER AND APPLICATION STATUS"
docker compose ps -a 2>&1 | Add-Content -LiteralPath $Report -Encoding utf8

try {
    $health = Invoke-WebRequest -UseBasicParsing -Uri "http://localhost:8000/health" -TimeoutSec 10
    "Backend health HTTP: $($health.StatusCode)" | Add-Content -LiteralPath $Report -Encoding utf8
} catch {
    "Backend health unavailable: $($_.Exception.Message)" | Add-Content -LiteralPath $Report -Encoding utf8
}

try {
    $openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 15
    $openapi.paths.PSObject.Properties.Name |
        Sort-Object |
        Where-Object { $_ -match "model|train|experiment|dataset|job|predict|registry|monitor" } |
        Add-Content -LiteralPath $Report -Encoding utf8
} catch {
    "OpenAPI unavailable: $($_.Exception.Message)" | Add-Content -LiteralPath $Report -Encoding utf8
}

Add-Section "PYTHON AND DEPENDENCY INVENTORY"
docker compose exec -T backend python --version 2>&1 |
    Add-Content -LiteralPath $Report -Encoding utf8

$Packages = @(
    "scikit-learn",
    "xgboost",
    "torch",
    "pandas",
    "numpy",
    "joblib",
    "pydantic",
    "sqlalchemy",
    "optuna",
    "fastapi"
)

foreach ($Package in $Packages) {
    "---- PACKAGE: $Package ----" | Add-Content -LiteralPath $Report -Encoding utf8
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $PackageOutput = docker compose exec -T backend python -m pip show $Package 2>&1
    $ExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousPreference

    if ($ExitCode -eq 0) {
        $PackageOutput | Add-Content -LiteralPath $Report -Encoding utf8
    } else {
        "MISSING" | Add-Content -LiteralPath $Report -Encoding utf8
    }
}

Add-Section "TRAINING AND MODEL SOURCE DISCOVERY"
$Patterns = @(
    "RandomForest", "XGB", "xgboost", "torch", "MLP", "ANN",
    "train_test_split", "GroupKFold", "GroupShuffleSplit", "TimeSeriesSplit",
    "joblib", "model_store", "experiment_store", "registry", "predict",
    "Experiment", "ModelVersion", "TrainingRun", "validation"
)

$BackendPath = Join-Path $ProjectRoot "backend"
if (Test-Path -LiteralPath $BackendPath) {
    $SourceFiles = Get-ChildItem `
        -LiteralPath $BackendPath `
        -Recurse -File -Include *.py,*.toml,*.txt,*.yml,*.yaml,*.json `
        -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch "\\(__pycache__|\.pytest_cache|\.venv|venv|node_modules)\\"
        }

    foreach ($Pattern in $Patterns) {
        "---- PATTERN: $Pattern ----" | Add-Content -LiteralPath $Report -Encoding utf8
        $SourceFiles |
            Select-String -Pattern $Pattern -SimpleMatch -ErrorAction SilentlyContinue |
            Select-Object Path, LineNumber, Line |
            Format-List |
            Out-String -Width 240 |
            Add-Content -LiteralPath $Report -Encoding utf8
    }
}

Add-Section "FRONTEND MODEL WORKSPACE DISCOVERY"
$FrontendSource = Join-Path $ProjectRoot "frontend\src"
if (Test-Path -LiteralPath $FrontendSource) {
    Get-ChildItem `
        -LiteralPath $FrontendSource `
        -Recurse -File -Include *.ts,*.tsx `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\(node_modules|dist)\\" } |
        Select-String -Pattern "Model Training|Model Registry|Experiment|Training|Prediction|Model Evaluation|Retrain" |
        Select-Object Path, LineNumber, Line |
        Format-List |
        Out-String -Width 240 |
        Add-Content -LiteralPath $Report -Encoding utf8
}

$Candidates = @(
    "docker-compose.yml",
    "backend\Dockerfile",
    "backend\pyproject.toml",
    "backend\requirements.txt",
    "backend\requirements-windows-dev.txt",
    "backend\alembic.ini",
    "backend\app\main.py",
    "backend\app\schemas.py",
    "backend\app\core\config.py",
    "backend\app\core\security.py",
    "backend\app\core\rbac.py",
    "backend\app\api\routes\platform.py",
    "backend\app\api\routes\models.py",
    "backend\app\api\routes\model_training.py",
    "backend\app\api\routes\experiments.py",
    "backend\app\api\routes\jobs.py",
    "backend\app\api\routes\monitoring.py",
    "backend\app\services\platform_service.py",
    "backend\app\services\model_service.py",
    "backend\app\services\training_service.py",
    "backend\app\repositories\model_repository.py",
    "backend\app\repositories\dataset_repository.py",
    "frontend\package.json",
    "frontend\src\features\dashboard\DashboardPage.tsx",
    "frontend\src\features\platform\platformApi.ts",
    "frontend\src\features\platform\ExperimentManagerPanel.tsx",
    "frontend\src\features\platform\ModelEvaluationPanel.tsx",
    "frontend\src\features\models\modelPlatformApi.ts",
    "frontend\src\features\models\ModelMonitoringPanel.tsx"
)

foreach ($Candidate in $Candidates) {
    Copy-RelativeFile $Candidate
}

$BackendApp = Join-Path $ProjectRoot "backend\app"
if (Test-Path -LiteralPath $BackendApp) {
    Get-ChildItem -LiteralPath $BackendApp -Recurse -File -Include *.py |
        Where-Object {
            $_.Name -match "model|train|experiment|dataset|job|registry|prediction" -and
            $_.FullName -notmatch "\\__pycache__\\"
        } |
        ForEach-Object {
            $Relative = $_.FullName.Substring($ProjectRoot.Length).TrimStart("\")
            Copy-RelativeFile $Relative
        }
}

if (Test-Path -LiteralPath $FrontendSource) {
    Get-ChildItem -LiteralPath $FrontendSource -Recurse -File -Include *.ts,*.tsx |
        Where-Object {
            $_.Name -match "Model|Train|Experiment|Dataset|Job|Registry|Prediction"
        } |
        ForEach-Object {
            $Relative = $_.FullName.Substring($ProjectRoot.Length).TrimStart("\")
            Copy-RelativeFile $Relative
        }
}

Add-Section "CAPTURED FILES"
Get-ChildItem -LiteralPath $OutputRoot -Recurse -File |
    Where-Object { $_.FullName -ne $Report } |
    ForEach-Object { $_.FullName.Substring($OutputRoot.Length).TrimStart("\") } |
    Sort-Object |
    Add-Content -LiteralPath $Report -Encoding utf8

if (Test-Path -LiteralPath $Bundle) {
    Remove-Item -LiteralPath $Bundle -Force
}

Compress-Archive -Path (Join-Path $OutputRoot "*") -DestinationPath $Bundle -CompressionLevel Optimal

$Hash = Get-FileHash -LiteralPath $Bundle -Algorithm SHA256
Add-Section "OUTPUT"
"Bundle: $Bundle" | Add-Content -LiteralPath $Report -Encoding utf8
"SHA256: $($Hash.Hash)" | Add-Content -LiteralPath $Report -Encoding utf8

Write-Host ""
Write-Host "Release 3 source preflight completed." -ForegroundColor Green
Write-Host "Upload this bundle in the chat:" -ForegroundColor Cyan
Write-Host $Bundle -ForegroundColor Yellow
Write-Host "SHA256: $($Hash.Hash)" -ForegroundColor DarkGray
