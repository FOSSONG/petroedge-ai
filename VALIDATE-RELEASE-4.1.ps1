$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Report = Join-Path $Root 'RELEASE-4.1-VALIDATION-REPORT.txt'
$Compose = 'docker compose'

function Write-Step([string]$Message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $Report -Value $line
}

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Remove-Item $Report -Force -ErrorAction SilentlyContinue
Write-Step 'PetroEdge AI Release 4.1 validation started.'
Assert-Command docker

try {
    Write-Step 'Validating Docker Compose configuration.'
    docker compose config --quiet

    Write-Step 'Building clean backend and frontend images.'
    docker compose build --no-cache

    Write-Step 'Starting the application stack.'
    docker compose up -d --remove-orphans

    Write-Step 'Waiting for backend health.'
    $healthy = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Start-Sleep -Seconds 4
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 8
            if ($health.status -in @('ok', 'degraded')) {
                $healthy = $true
                break
            }
        } catch {
            Write-Host "Health attempt $attempt/30 not ready." -ForegroundColor DarkYellow
        }
    }
    if (-not $healthy) {
        throw 'Backend did not become healthy.'
    }

    Write-Step 'Confirming model-lifecycle route registration.'
    $openApi = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 15
    $requiredPaths = @(
        '/api/v1/training-lifecycle/algorithms',
        '/api/v1/training-lifecycle/train',
        '/api/v1/training-lifecycle/registry',
        '/api/v1/training-lifecycle/predict',
        '/api/v1/training-lifecycle/registry/{model_id}/stage',
        '/api/v1/training-lifecycle/registry/{model_id}/retrain'
    )
    foreach ($path in $requiredPaths) {
        if (-not $openApi.paths.PSObject.Properties.Name.Contains($path)) {
            throw "Missing OpenAPI route: $path"
        }
    }

    Write-Step 'Confirming frontend HTTP response.'
    $frontend = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 15
    if ($frontend.StatusCode -ne 200) {
        throw "Frontend returned HTTP $($frontend.StatusCode)."
    }

    Write-Step 'Validation PASSED.'
    docker compose ps | Out-String | Add-Content -Path $Report
    Write-Host "`nRelease 4.1 validation passed. Report: $Report" -ForegroundColor Green
}
catch {
    Write-Step "Validation FAILED: $($_.Exception.Message)"
    docker compose ps -a | Out-String | Add-Content -Path $Report
    docker compose logs --no-color --tail 250 | Out-String | Add-Content -Path $Report
    Write-Host "`nValidation failed. Existing source files were not modified by this validator." -ForegroundColor Red
    Write-Host "Report: $Report" -ForegroundColor Yellow
    exit 1
}
