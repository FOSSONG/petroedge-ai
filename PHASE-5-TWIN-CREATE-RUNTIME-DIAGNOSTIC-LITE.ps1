$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Report = Join-Path $Root "PHASE-5-TWIN-CREATE-RUNTIME-DIAGNOSTIC-LITE.txt"
$Panel = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Twins = Join-Path $Root "backend\app\api\routes\twins.py"

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Project folder not found: $Root"
}

Set-Location $Root

"PETROEDGE AI PHASE 5 TWIN CREATE RUNTIME DIAGNOSTIC LITE" |
    Set-Content -LiteralPath $Report -Encoding utf8
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')" |
    Add-Content -LiteralPath $Report -Encoding utf8
"Project: $Root" |
    Add-Content -LiteralPath $Report -Encoding utf8

function Add-Section {
    param([string]$Title)
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ""
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ("=" * 100)
    Add-Content -LiteralPath $Report -Encoding utf8 -Value $Title
    Add-Content -LiteralPath $Report -Encoding utf8 -Value ("=" * 100)
}

function Run-External {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 20
    )

    $Stdout = [System.IO.Path]::GetTempFileName()
    $Stderr = [System.IO.Path]::GetTempFileName()

    try {
        $Process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $Stdout `
            -RedirectStandardError $Stderr

        if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $Process.Kill() } catch {}
            Add-Content -LiteralPath $Report -Encoding utf8 `
                -Value "TIMEOUT after $TimeoutSeconds seconds: $FilePath $($Arguments -join ' ')"
            return
        }

        if (Test-Path $Stdout) {
            Get-Content $Stdout -ErrorAction SilentlyContinue |
                Add-Content -LiteralPath $Report -Encoding utf8
        }

        if (Test-Path $Stderr) {
            Get-Content $Stderr -ErrorAction SilentlyContinue |
                Add-Content -LiteralPath $Report -Encoding utf8
        }

        Add-Content -LiteralPath $Report -Encoding utf8 `
            -Value "Exit code: $($Process.ExitCode)"
    }
    catch {
        Add-Content -LiteralPath $Report -Encoding utf8 `
            -Value "ERROR: $($_.Exception.Message)"
    }
    finally {
        Remove-Item $Stdout, $Stderr -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "[1/7] Writing report immediately..." -ForegroundColor Cyan
Add-Section "DOCKER STATUS"
Run-External -FilePath "docker" -Arguments @("compose", "ps", "-a") -TimeoutSeconds 15

Write-Host "[2/7] Checking backend health..." -ForegroundColor Cyan
Add-Section "BACKEND HEALTH"
try {
    $Health = Invoke-RestMethod `
        -Uri "http://localhost:8000/health" `
        -TimeoutSec 10

    $Health |
        ConvertTo-Json -Depth 10 |
        Add-Content -LiteralPath $Report -Encoding utf8
}
catch {
    "ERROR: $($_.Exception.Message)" |
        Add-Content -LiteralPath $Report -Encoding utf8
}

Write-Host "[3/7] Checking OpenAPI schema..." -ForegroundColor Cyan
Add-Section "OPENAPI DIGITAL TWIN ROUTES AND SCHEMA"
try {
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -TimeoutSec 15

    foreach ($ApiPath in @(
        "/api/v1/twins",
        "/api/v1/twins/{reservoir_id}",
        "/api/v1/twin-workspace/{reservoir_id}/summary"
    )) {
        $Property = $OpenApi.paths.PSObject.Properties[$ApiPath]

        if ($null -eq $Property) {
            "MISSING: $ApiPath" |
                Add-Content -LiteralPath $Report -Encoding utf8
        }
        else {
            $Methods = @($Property.Value.PSObject.Properties.Name) -join ", "
            "$ApiPath -> $Methods" |
                Add-Content -LiteralPath $Report -Encoding utf8
        }
    }

    if ($null -ne $OpenApi.components.schemas.TwinCreate) {
        "TwinCreate schema:" |
            Add-Content -LiteralPath $Report -Encoding utf8

        $OpenApi.components.schemas.TwinCreate |
            ConvertTo-Json -Depth 12 |
            Add-Content -LiteralPath $Report -Encoding utf8
    }
}
catch {
    "ERROR: $($_.Exception.Message)" |
        Add-Content -LiteralPath $Report -Encoding utf8
}

Write-Host "[4/7] Checking host source markers..." -ForegroundColor Cyan
Add-Section "HOST SOURCE MARKERS"

if (Test-Path -LiteralPath $Twins) {
    Get-Content -LiteralPath $Twins |
        Select-String -Pattern "READ_ROLES|WRITE_ROLES|def create_twin" |
        ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" } |
        Add-Content -LiteralPath $Report -Encoding utf8
}
else {
    "MISSING: $Twins" |
        Add-Content -LiteralPath $Report -Encoding utf8
}

if (Test-Path -LiteralPath $Panel) {
    foreach ($Marker in @(
        "fetchAssets",
        "Source asset",
        "No reservoir twin exists yet",
        "twins.isError",
        "setCreateOpen(true)"
    )) {
        $Matches = Select-String `
            -LiteralPath $Panel `
            -Pattern $Marker `
            -SimpleMatch

        if ($Matches) {
            foreach ($Match in $Matches) {
                "$Marker -> line $($Match.LineNumber)" |
                    Add-Content -LiteralPath $Report -Encoding utf8
            }
        }
        else {
            "$Marker -> NOT FOUND" |
                Add-Content -LiteralPath $Report -Encoding utf8
        }
    }
}

Write-Host "[5/7] Checking active container files..." -ForegroundColor Cyan
Add-Section "ACTIVE BACKEND ROLE DEFINITIONS"
Run-External `
    -FilePath "docker" `
    -Arguments @(
        "compose", "exec", "-T", "backend",
        "sh", "-lc",
        "grep -nE 'READ_ROLES|WRITE_ROLES|def create_twin' /app/app/api/routes/twins.py || true"
    ) `
    -TimeoutSeconds 15

Add-Section "ACTIVE FRONTEND BUNDLE MARKERS"
Run-External `
    -FilePath "docker" `
    -Arguments @(
        "compose", "exec", "-T", "frontend",
        "sh", "-lc",
        "grep -R -l -m 1 'Source asset' /usr/share/nginx/html/assets 2>/dev/null || true; grep -R -l -m 1 'No reservoir twin exists yet' /usr/share/nginx/html/assets 2>/dev/null || true; grep -R -l -m 1 'Create reservoir twin' /usr/share/nginx/html/assets 2>/dev/null || true"
    ) `
    -TimeoutSeconds 20

Write-Host "[6/7] Collecting recent backend errors..." -ForegroundColor Cyan
Add-Section "RECENT BACKEND TWIN REQUESTS"
Run-External `
    -FilePath "docker" `
    -Arguments @(
        "compose", "logs", "backend",
        "--since", "20m",
        "--tail", "500"
    ) `
    -TimeoutSeconds 20

Write-Host "[7/7] Recording interpretation notes..." -ForegroundColor Cyan
Add-Section "INTERPRETATION"
@(
    "If host frontend markers exist but container bundle markers do not, the frontend image is stale."
    "If both marker sets exist, inspect recent backend logs for 401, 403, 409, 422 or 500 responses."
    "If /api/v1/twins is missing from OpenAPI, route registration failed."
    "If TwinCreate requires fields beyond reservoir_id and name, the frontend payload must be expanded."
    "This report is written incrementally, so it remains available even if a later step times out."
) | Add-Content -LiteralPath $Report -Encoding utf8

Write-Host ""
Write-Host "DIAGNOSTIC COMPLETED" -ForegroundColor Green
Write-Host "Report: $Report"
