$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
docker compose stop
if ($LASTEXITCODE -ne 0) { throw "PetroEdge could not be stopped." }
Write-Host "PetroEdge AI stopped." -ForegroundColor Green
