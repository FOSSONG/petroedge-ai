param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),
    [switch]$ExportDockerImages
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $ProjectRoot "backups\working-$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

Write-Host "Saving resolved Docker Compose configuration..."
docker compose config | Out-File (Join-Path $backupRoot "docker-compose-resolved.yml") -Encoding utf8

$paths = @(
    "docker-compose.yml",
    "frontend\nginx.conf",
    "backend\data",
    "backend\dataset_store",
    "backend\model_store",
    "backend\experiment_store",
    "backend\petroedge.db"
)

foreach ($relativePath in $paths) {
    $source = Join-Path $ProjectRoot $relativePath
    if (Test-Path $source) {
        Write-Host "Backing up $relativePath"
        Copy-Item -Path $source -Destination $backupRoot -Recurse -Force
    }
}

$gitStatus = git status --porcelain 2>$null
$gitStatus | Out-File (Join-Path $backupRoot "git-status.txt") -Encoding utf8
$gitHead = git rev-parse HEAD 2>$null
$gitHead | Out-File (Join-Path $backupRoot "git-head.txt") -Encoding utf8

if ($ExportDockerImages) {
    Write-Host "Exporting currently deployed Docker images..."
    $backendImage = docker inspect petroedge-mvp-backend --format '{{.Image}}' 2>$null
    $frontendImage = docker inspect petroedge-mvp-frontend --format '{{.Image}}' 2>$null

    if ($backendImage -and $frontendImage) {
        docker save -o (Join-Path $backupRoot "petroedge-working-images.tar") $backendImage $frontendImage
    } else {
        Write-Warning "Running PetroEdge containers were not found. Docker images were not exported."
    }
}

Write-Host "Backup complete: $backupRoot" -ForegroundColor Green
