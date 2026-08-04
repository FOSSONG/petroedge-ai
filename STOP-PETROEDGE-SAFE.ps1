$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"

Set-Location $ProjectRoot

docker compose stop backend frontend

if ($LASTEXITCODE -ne 0) {
    throw "PetroEdge could not be stopped cleanly."
}

docker compose ps -a

Write-Host ""
Write-Host "PetroEdge stopped." -ForegroundColor Green
Write-Host "Datasets, models, database and images were preserved." -ForegroundColor Green