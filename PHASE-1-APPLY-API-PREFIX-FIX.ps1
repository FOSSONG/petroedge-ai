$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\phase1-api-prefix-$Timestamp"
$ReportPath = Join-Path $ProjectRoot "PHASE-1-API-PREFIX-RESULT.txt"

$ReservoirRouteFile = Join-Path $ProjectRoot "backend\app\api\routes\reservoir_v1.py"
$PlatformApiFile = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts"

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

function Save-Backup {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$RelativeDestination
    )

    $Destination = Join-Path $BackupRoot $RelativeDestination
    $DestinationDirectory = Split-Path -Parent $Destination

    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Replace-ExactlyOnce {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$OldText,
        [Parameter(Mandatory = $true)][string]$NewText,
        [Parameter(Mandatory = $true)][string]$Description
    )

    $Content = [System.IO.File]::ReadAllText($Path)
    $FirstIndex = $Content.IndexOf($OldText, [System.StringComparison]::Ordinal)

    if ($FirstIndex -lt 0) {
        if ($Content.Contains($NewText)) {
            Write-Host "$Description is already corrected." -ForegroundColor Yellow
            return
        }

        throw "Expected text was not found for: $Description"
    }

    $SecondIndex = $Content.IndexOf(
        $OldText,
        $FirstIndex + $OldText.Length,
        [System.StringComparison]::Ordinal
    )

    if ($SecondIndex -ge 0) {
        throw "More than one match was found for: $Description. No automatic change was made."
    }

    $Updated = $Content.Substring(0, $FirstIndex) +
        $NewText +
        $Content.Substring($FirstIndex + $OldText.Length)

    [System.IO.File]::WriteAllText(
        $Path,
        $Updated,
        (New-Object System.Text.UTF8Encoding($false))
    )

    Write-Host "Corrected: $Description" -ForegroundColor Green
}

Assert-FileExists -Path $ReservoirRouteFile
Assert-FileExists -Path $PlatformApiFile

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

Save-Backup `
    -Source $ReservoirRouteFile `
    -RelativeDestination "backend\app\api\routes\reservoir_v1.py"

Save-Backup `
    -Source $PlatformApiFile `
    -RelativeDestination "frontend\src\features\platform\platformApi.ts"

Write-Host ""
Write-Host "[1/6] Correcting backend router prefix..." -ForegroundColor Cyan

Replace-ExactlyOnce `
    -Path $ReservoirRouteFile `
    -OldText 'router = APIRouter(prefix="/v1", tags=["Reservoir Intelligence V1"])' `
    -NewText 'router = APIRouter(tags=["Reservoir Intelligence V1"])' `
    -Description 'reservoir_v1 router prefix /v1 -> empty'

Write-Host ""
Write-Host "[2/6] Correcting frontend Assets paths..." -ForegroundColor Cyan

Replace-ExactlyOnce `
    -Path $PlatformApiFile `
    -OldText 'apiRequest<Array<{asset_id:string;field:string;well:string;dataset_id?:string|null;status:string}>>(`/v1/assets`)' `
    -NewText 'apiRequest<Array<{asset_id:string;field:string;well:string;dataset_id?:string|null;status:string}>>(`/assets`)' `
    -Description 'fetchAssets /v1/assets -> /assets'

Replace-ExactlyOnce `
    -Path $PlatformApiFile `
    -OldText 'apiRequest(`/v1/assets`,{method:"POST",body:JSON.stringify(payload)})' `
    -NewText 'apiRequest(`/assets`,{method:"POST",body:JSON.stringify(payload)})' `
    -Description 'saveAsset /v1/assets -> /assets'

Set-Location $ProjectRoot

Write-Host ""
Write-Host "[3/6] Validating Docker Compose..." -ForegroundColor Cyan

docker compose config --quiet

if ($LASTEXITCODE -ne 0) {
    throw "docker-compose.yml validation failed."
}

Write-Host ""
Write-Host "[4/6] Rebuilding PetroEdge..." -ForegroundColor Cyan

docker compose up -d --build --force-recreate --remove-orphans

if ($LASTEXITCODE -ne 0) {
    throw "Docker rebuild failed. Original files are preserved in: $BackupRoot"
}

Write-Host ""
Write-Host "[5/6] Waiting for backend health..." -ForegroundColor Cyan

$BackendHealthy = $false

for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
    $BackendId = docker compose ps -q backend 2>$null

    if ($BackendId) {
        $Status = docker inspect $BackendId --format "{{.State.Status}}" 2>$null
        $Health = docker inspect $BackendId --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}" 2>$null

        Write-Host "Backend: status=$Status health=$Health"

        if ($Status -eq "running" -and ($Health -eq "healthy" -or $Health -eq "no-healthcheck")) {
            $BackendHealthy = $true
            break
        }
    }
    else {
        Write-Host "Backend container has not been created yet."
    }

    Start-Sleep -Seconds 4
}

if (-not $BackendHealthy) {
    docker compose ps -a
    docker compose logs backend --tail 250
    throw "Backend failed to become healthy. Backups: $BackupRoot"
}

Write-Host ""
Write-Host "[6/6] Validating canonical API paths..." -ForegroundColor Cyan

$OpenApi = Invoke-RestMethod `
    -Uri "http://localhost:8000/openapi.json" `
    -Method Get `
    -TimeoutSec 30

$Paths = @($OpenApi.paths.PSObject.Properties.Name | Sort-Object)
$DuplicatedPaths = @($Paths | Where-Object { $_ -like "/api/v1/v1/*" })

$ExpectedCanonicalPaths = @(
    "/api/v1/datasets/{dataset_id}/assistant",
    "/api/v1/datasets/{dataset_id}/interpretation",
    "/api/v1/datasets/{dataset_id}/las-wizard",
    "/api/v1/datasets/{dataset_id}/replay",
    "/api/v1/datasets/{dataset_id}/report.pdf",
    "/api/v1/edge-runtime",
    "/api/v1/modules"
)

$MissingCanonicalPaths = @(
    $ExpectedCanonicalPaths |
        Where-Object { $Paths -notcontains $_ }
)

$Result = New-Object System.Collections.Generic.List[string]
$Result.Add("PETROEDGE AI PHASE 1 API PREFIX RESULT")
$Result.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Result.Add("Backup: $BackupRoot")
$Result.Add("")
$Result.Add("Duplicated /api/v1/v1 paths remaining: $($DuplicatedPaths.Count)")

foreach ($Path in $DuplicatedPaths) {
    $Result.Add("DUPLICATED: $Path")
}

$Result.Add("")
$Result.Add("Missing expected canonical paths: $($MissingCanonicalPaths.Count)")

foreach ($Path in $MissingCanonicalPaths) {
    $Result.Add("MISSING: $Path")
}

$Result.Add("")
$Result.Add("Assets route currently registered: $($Paths -contains '/api/v1/assets')")
$Result.Add("")
$Result.Add("Docker state:")

$ComposeState = docker compose ps -a 2>&1

foreach ($Line in $ComposeState) {
    $Result.Add([string]$Line)
}

$Result | Set-Content -LiteralPath $ReportPath -Encoding utf8

if ($DuplicatedPaths.Count -gt 0) {
    throw "Duplicated API paths remain. Review: $ReportPath"
}

if ($MissingCanonicalPaths.Count -gt 0) {
    throw "One or more canonical routes are missing. Review: $ReportPath"
}

Write-Host ""
Write-Host "PHASE 1 API PREFIX CORRECTION COMPLETED" -ForegroundColor Green
Write-Host "No /api/v1/v1 routes remain." -ForegroundColor Green
Write-Host "Result report: $ReportPath"
Write-Host "Backups: $BackupRoot"
Write-Host ""
Write-Host "Important: /api/v1/assets is not yet implemented in the backend." -ForegroundColor Yellow
Write-Host "That endpoint will be added in Phase 2." -ForegroundColor Yellow
