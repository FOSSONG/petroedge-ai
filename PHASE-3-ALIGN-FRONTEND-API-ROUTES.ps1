$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "patch-backups\phase3-frontend-route-alignment-$Timestamp"
$ResultPath = Join-Path $ProjectRoot "PHASE-3-FRONTEND-ROUTE-ALIGNMENT-RESULT.txt"
$PlatformApiFile = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts"

function Assert-FileExists {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Replace-Required {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$OldText,
        [Parameter(Mandatory = $true)][string]$NewText,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if ($Content.Contains($OldText)) {
        Write-Host "Correcting: $Description" -ForegroundColor Green
        return $Content.Replace($OldText, $NewText)
    }

    if ($Content.Contains($NewText)) {
        Write-Host "Already corrected: $Description" -ForegroundColor Yellow
        return $Content
    }

    throw "Expected route text was not found for: $Description"
}

Assert-FileExists -Path $PlatformApiFile

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Copy-Item `
    -LiteralPath $PlatformApiFile `
    -Destination (Join-Path $BackupRoot "platformApi.ts") `
    -Force

Write-Host ""
Write-Host "[1/6] Correcting canonical frontend API paths..." -ForegroundColor Cyan

$Content = [System.IO.File]::ReadAllText($PlatformApiFile)

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/datasets/${datasetId}/interpretation`' `
    -NewText '`/datasets/${datasetId}/interpretation`' `
    -Description "Reservoir interpretation"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/datasets/${datasetId}/las-wizard`' `
    -NewText '`/datasets/${datasetId}/las-wizard`' `
    -Description "LAS wizard"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/datasets/${datasetId}/replay?${params.toString()}`' `
    -NewText '`/datasets/${datasetId}/replay?${params.toString()}`' `
    -Description "Dataset replay"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/datasets/${datasetId}/assistant`' `
    -NewText '`/datasets/${datasetId}/assistant`' `
    -Description "AI assistant"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/edge-runtime`' `
    -NewText '`/edge-runtime`' `
    -Description "Edge runtime"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`/v1/modules`' `
    -NewText '`/modules`' `
    -Description "Module framework"

$Content = Replace-Required `
    -Content $Content `
    -OldText '`${base}/v1/datasets/${datasetId}/report.pdf`' `
    -NewText '`${base}/datasets/${datasetId}/report.pdf`' `
    -Description "Reservoir PDF download"

Write-Utf8NoBom -Path $PlatformApiFile -Content $Content

Write-Host ""
Write-Host "[2/6] Checking for stale /v1 frontend paths..." -ForegroundColor Cyan

$StaleMatches = Select-String `
    -LiteralPath $PlatformApiFile `
    -Pattern '["''`]\/v1\/' `
    -CaseSensitive:$false

if ($StaleMatches) {
    foreach ($Match in $StaleMatches) {
        Write-Host "$($Match.LineNumber): $($Match.Line.Trim())" -ForegroundColor Red
    }

    throw "Stale /v1 frontend API paths remain in platformApi.ts."
}

Set-Location $ProjectRoot

Write-Host ""
Write-Host "[3/6] Validating Docker Compose..." -ForegroundColor Cyan

docker compose config --quiet

if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host ""
Write-Host "[4/6] Rebuilding the frontend..." -ForegroundColor Cyan

docker compose up -d --build frontend

if ($LASTEXITCODE -ne 0) {
    throw "Frontend rebuild failed. Backup: $BackupRoot"
}

Write-Host ""
Write-Host "[5/6] Confirming container and API health..." -ForegroundColor Cyan

$Healthy = $false

for ($Attempt = 1; $Attempt -le 25; $Attempt++) {
    try {
        $Health = Invoke-RestMethod `
            -Uri "http://localhost:8000/health" `
            -Method Get `
            -TimeoutSec 10

        if ($Health.status -in @("ok", "healthy", "degraded")) {
            $Healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $Healthy) {
    docker compose ps -a
    docker compose logs backend --tail 200
    throw "Backend health verification failed."
}

$OpenApi = Invoke-RestMethod `
    -Uri "http://localhost:8000/openapi.json" `
    -Method Get `
    -TimeoutSec 30

$Paths = @($OpenApi.paths.PSObject.Properties.Name)

$RequiredPaths = @(
    "/api/v1/assets",
    "/api/v1/datasets/{dataset_id}/interpretation",
    "/api/v1/datasets/{dataset_id}/las-wizard",
    "/api/v1/datasets/{dataset_id}/replay",
    "/api/v1/datasets/{dataset_id}/assistant",
    "/api/v1/datasets/{dataset_id}/report.pdf",
    "/api/v1/edge-runtime",
    "/api/v1/modules"
)

$Missing = @($RequiredPaths | Where-Object { $Paths -notcontains $_ })
$Duplicated = @($Paths | Where-Object { $_ -like "/api/v1/v1/*" })

Write-Host ""
Write-Host "[6/6] Writing verification report..." -ForegroundColor Cyan

$Result = New-Object System.Collections.Generic.List[string]
$Result.Add("PETROEDGE AI PHASE 3 FRONTEND ROUTE ALIGNMENT RESULT")
$Result.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Result.Add("Backup: $BackupRoot")
$Result.Add("")
$Result.Add("Missing required canonical paths: $($Missing.Count)")

foreach ($Path in $Missing) {
    $Result.Add("MISSING: $Path")
}

$Result.Add("")
$Result.Add("Duplicated /api/v1/v1 paths: $($Duplicated.Count)")

foreach ($Path in $Duplicated) {
    $Result.Add("DUPLICATED: $Path")
}

$Result.Add("")
$Result.Add("Assets route registered: $($Paths -contains '/api/v1/assets')")
$Result.Add("OpenAPI path count: $($Paths.Count)")
$Result.Add("")
$Result.Add("Docker state:")

$ComposeState = docker compose ps -a 2>&1

foreach ($Line in $ComposeState) {
    $Result.Add([string]$Line)
}

$Result | Set-Content -LiteralPath $ResultPath -Encoding utf8

if ($Missing.Count -gt 0) {
    throw "Required backend routes are missing. Review: $ResultPath"
}

if ($Duplicated.Count -gt 0) {
    throw "Duplicated backend routes remain. Review: $ResultPath"
}

Write-Host ""
Write-Host "PHASE 3 FRONTEND ROUTE ALIGNMENT COMPLETED" -ForegroundColor Green
Write-Host "The Assets, Reservoir Intelligence, LAS Wizard, Replay," -ForegroundColor Green
Write-Host "AI Assistant, Edge Runtime and Modules calls now use canonical paths." -ForegroundColor Green
Write-Host ""
Write-Host "Result report: $ResultPath"
Write-Host "Backup: $BackupRoot"
Write-Host ""
Write-Host "Refresh the browser with Ctrl+F5." -ForegroundColor Yellow
