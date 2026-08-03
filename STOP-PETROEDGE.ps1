$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
docker compose stop

if ($LASTEXITCODE -ne 0) {
    throw "PetroEdge could not be stopped cleanly."
}

docker compose ps -a
Write-Host "PetroEdge AI stopped." -ForegroundColor Green