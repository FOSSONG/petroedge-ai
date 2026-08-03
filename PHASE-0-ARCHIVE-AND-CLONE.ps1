$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SourceRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-2.3-WORKING-20260729-2310\PetroEdge-AI-Release-2.3-Unified-Data-Lineage-Reporting"
$DocumentsRoot = "C:\Users\GUILIANNO FOSSONG\Documents"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$StableRoot = Join-Path $DocumentsRoot "PetroEdge-AI-Release-2.3-STABLE-$Timestamp"
$Release4Root = Join-Path $DocumentsRoot "PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ValidationLog = Join-Path $SourceRoot "PHASE-0-VALIDATION-$Timestamp.txt"

function Step([string]$Message) {
    Write-Host ""
    Write-Host $Message -ForegroundColor Cyan
}

function Check-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function Copy-Project([string]$Source, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) {
        throw "Destination already exists: $Destination"
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null

    & robocopy $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /XJ /FFT /NP /NFL /NDL `
        /XD .git .venv node_modules dist __pycache__ .pytest_cache .mypy_cache .ruff_cache `
        /XF *.pyc *.pyo *.tmp

    $Code = $LASTEXITCODE
    if ($Code -gt 7) {
        throw "Robocopy failed with exit code $Code."
    }
    $global:LASTEXITCODE = 0
}

function Wait-Http([string]$Url) {
    for ($Attempt = 1; $Attempt -le 30; $Attempt++) {
        try {
            $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 400) {
                return $Response
            }
        }
        catch {
            if ($Attempt -eq 30) {
                throw "HTTP validation failed for $Url. $($_.Exception.Message)"
            }
            Start-Sleep -Seconds 4
        }
    }
}

try {
    Step "[1/9] Validating project"

    $Required = @(
        $SourceRoot,
        (Join-Path $SourceRoot "docker-compose.yml"),
        (Join-Path $SourceRoot "backend\Dockerfile"),
        (Join-Path $SourceRoot "backend\app\main.py"),
        (Join-Path $SourceRoot "frontend\Dockerfile"),
        (Join-Path $SourceRoot "frontend\package.json")
    )

    foreach ($Path in $Required) {
        if (-not (Test-Path -LiteralPath $Path)) {
            throw "Required path not found: $Path"
        }
    }

    if (Test-Path -LiteralPath $Release4Root) {
        throw "Release 4 destination already exists: $Release4Root"
    }

    Step "[2/9] Verifying Docker"
    & docker --version
    Check-Exit "Docker validation"
    & docker compose version
    Check-Exit "Docker Compose validation"

    Step "[3/9] Validating Compose configuration"
    Push-Location $SourceRoot
    try {
        & docker compose config --quiet
        Check-Exit "Docker Compose configuration validation"
        & docker compose down
        Check-Exit "Current stack shutdown"
    }
    finally {
        Pop-Location
    }

    Step "[4/9] Creating Release 2.3 archive"
    Copy-Project $SourceRoot $StableRoot

    Step "[5/9] Creating Release 4 workspace"
    Copy-Project $StableRoot $Release4Root

    Get-ChildItem -LiteralPath $Release4Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "*.before-*" -or
            $_.Name -like "*.bak" -or
            $_.Name -like "*.orig"
        } |
        Remove-Item -Force

    Get-ChildItem -LiteralPath $Release4Root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force

    @(
        "PetroEdge AI Release 2.3 archived baseline",
        "Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
        "Source: $SourceRoot",
        "Archive: $StableRoot",
        "Do not modify this archived directory."
    ) | Set-Content -LiteralPath (Join-Path $StableRoot "RELEASE-2.3-ARCHIVE-STATUS.txt") -Encoding utf8

    @(
        "PetroEdge AI Release 4.0 development workspace",
        "Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
        "Baseline: $StableRoot",
        "Final API rule: /api/v1 only",
        "Phase 1: routing",
        "Phase 2: Assets, Fields and Wells"
    ) | Set-Content -LiteralPath (Join-Path $Release4Root "RELEASE-4.0-WORKSPACE-STATUS.txt") -Encoding utf8

    Step "[6/9] Building archived baseline"
    Push-Location $StableRoot
    try {
        & docker compose build backend frontend
        Check-Exit "Docker build"
    }
    finally {
        Pop-Location
    }

    Step "[7/9] Starting archived baseline"
    Push-Location $StableRoot
    try {
        & docker compose up -d
        Check-Exit "Docker startup"

        $ContainerPython = & docker compose exec -T backend python --version 2>&1
        Check-Exit "Backend Python check"
        Write-Host "Backend container: $ContainerPython" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }

    Step "[8/9] Validating application"
    $Frontend = Wait-Http "http://localhost:5173/"
    $Health = Wait-Http "http://localhost:8000/health"
    $OpenApiResponse = Wait-Http "http://localhost:8000/openapi.json"
    $OpenApi = $OpenApiResponse.Content | ConvertFrom-Json
    $Paths = @($OpenApi.paths.PSObject.Properties.Name)
    $Legacy = @($Paths | Where-Object { $_ -like "/api/v1/v1*" })
    $Assets = @($Paths | Where-Object { $_ -like "*assets*" })

    $LegacyText = if ($Legacy.Count -gt 0) { $Legacy -join "; " } else { "None" }
    $AssetsText = if ($Assets.Count -gt 0) { $Assets -join "; " } else { "None" }

    @(
        "=== PHASE 0 VALIDATION ===",
        "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
        "Backend container Python: $ContainerPython",
        "Frontend status: $($Frontend.StatusCode)",
        "Backend health status: $($Health.StatusCode)",
        "OpenAPI status: $($OpenApiResponse.StatusCode)",
        "Stable archive: $StableRoot",
        "Release 4 workspace: $Release4Root",
        "Legacy routes: $LegacyText",
        "Assets routes: $AssetsText"
    ) | Set-Content -LiteralPath $ValidationLog -Encoding utf8

    Copy-Item $ValidationLog (Join-Path $StableRoot "PHASE-0-VALIDATION.txt") -Force
    Copy-Item $ValidationLog (Join-Path $Release4Root "PHASE-0-BASELINE-VALIDATION.txt") -Force

    Step "[9/9] Completed"
    Write-Host "PHASE 0 COMPLETED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "Archived Release 2.3: $StableRoot"
    Write-Host "Release 4 workspace: $Release4Root"
    Write-Host "Validation report: $ValidationLog"
}
catch {
    Write-Host ""
    Write-Host "PHASE 0 FAILED" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red

    if (Test-Path -LiteralPath $Release4Root) {
        Remove-Item -LiteralPath $Release4Root -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path -LiteralPath $StableRoot) {
        Push-Location $StableRoot
        try { & docker compose down 2>$null } catch { }
        finally { Pop-Location }
        Remove-Item -LiteralPath $StableRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (Test-Path -LiteralPath $SourceRoot) {
        Push-Location $SourceRoot
        try { & docker compose up -d } catch { }
        finally { Pop-Location }
    }

    exit 1
}
