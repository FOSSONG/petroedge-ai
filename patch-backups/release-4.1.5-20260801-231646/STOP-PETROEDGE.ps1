$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Set-Location $PSScriptRoot

docker compose down

if ($LASTEXITCODE -ne 0) {
    throw "PetroEdge shutdown failed."
}

Write-Host "PetroEdge AI stopped successfully." -ForegroundColor Green