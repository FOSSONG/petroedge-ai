$ErrorActionPreference = "Stop"
Write-Host "Validating PetroEdge AI Release 4.1.2" -ForegroundColor Cyan
docker compose config | Out-Null
docker compose build --no-cache
docker compose down --remove-orphans
docker rm -f petroedge-mvp-backend petroedge-mvp-frontend 2>$null | Out-Null
docker compose up -d
Start-Sleep -Seconds 20
docker compose ps -a
docker compose logs backend --tail 120
$openapi = Invoke-RestMethod "http://localhost:8000/openapi.json" -TimeoutSec 30
$required = @(
  "/api/v1/platform/datasets/{dataset_id}/quality",
  "/api/v1/platform/datasets/{dataset_id}/prepare",
  "/api/v1/platform/datasets/{dataset_id}/edit",
  "/api/v1/platform/datasets/{dataset_id}/download",
  "/api/v1/training-lifecycle/predictions/{output_name}/download"
)
foreach ($route in $required) {
  if ($openapi.paths.PSObject.Properties.Name -notcontains $route) { throw "Missing route: $route" }
}
Write-Host "Release 4.1.2 validation passed." -ForegroundColor Green
