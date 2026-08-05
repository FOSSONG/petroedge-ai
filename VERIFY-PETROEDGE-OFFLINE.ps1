$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
Set-Location $ProjectRoot

$Results = [ordered]@{
    docker_engine = $false
    compose_valid = $false
    backend_image = $false
    frontend_image = $false
    database_present = $false
    model_store_present = $false
    dataset_store_present = $false
    offline_startup_ready = $false
}

docker info *> $null
$Results.docker_engine = $LASTEXITCODE -eq 0

docker compose `
    -f docker-compose.yml `
    -f compose.offline.yml `
    config --quiet
$Results.compose_valid = $LASTEXITCODE -eq 0

docker image inspect petroedge-release45-backend *> $null
$Results.backend_image = $LASTEXITCODE -eq 0

docker image inspect petroedge-release45-frontend *> $null
$Results.frontend_image = $LASTEXITCODE -eq 0

$Results.database_present = Test-Path ".\backend\data\petroedge.db"
$Results.model_store_present = Test-Path ".\backend\model_store"
$Results.dataset_store_present = Test-Path ".\backend\dataset_store"

$Results.offline_startup_ready = (
    $Results.docker_engine -and
    $Results.compose_valid -and
    $Results.backend_image -and
    $Results.frontend_image
)

$Results | ConvertTo-Json

if (-not $Results.offline_startup_ready) {
    throw "PetroEdge is not ready for offline startup."
}

Write-Host "PETROEDGE OFFLINE READINESS PASSED" -ForegroundColor Green