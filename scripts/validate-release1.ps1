param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

Write-Host "Validating Docker Compose configuration..."
docker compose config | Out-Null

Write-Host "Building PetroEdge containers..."
docker compose build

Write-Host "Starting PetroEdge containers..."
docker compose up -d --force-recreate

docker compose ps

Write-Host "Checking frontend..."
$frontend = Invoke-WebRequest "http://localhost:5173" -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "Frontend check failed." }

Write-Host "Checking backend health..."
$health = Invoke-RestMethod "http://localhost:8000/health"
if ($health.status -notin @("ok", "degraded")) { throw "Backend health check failed: $($health.status)" }

Write-Host "Checking Nginx API proxy..."
try {
    Invoke-WebRequest "http://localhost:5173/api/v1/auth/me" -UseBasicParsing | Out-Null
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw }
}

Write-Host "Release 1 validation passed." -ForegroundColor Green
