$ErrorActionPreference = "Stop"

Write-Host "Checking Release 2 containers..." -ForegroundColor Cyan
docker compose ps

Write-Host "Checking backend health..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 15 | Out-Null

Write-Host "Checking Edge Computing capabilities..." -ForegroundColor Cyan
$caps = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/edge/capabilities" -TimeoutSec 15
if (-not $caps.edge_ready) { throw "Edge Computing capability is not ready." }

Write-Host "Checking Edge Computing dashboard..." -ForegroundColor Cyan
$dashboard = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/edge/dashboard" -TimeoutSec 15
if ($null -eq $dashboard.summary.registered_devices) { throw "Edge dashboard response is invalid." }

Write-Host "Checking frontend..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 15 | Out-Null

Write-Host "Release 2 validation passed." -ForegroundColor Green
