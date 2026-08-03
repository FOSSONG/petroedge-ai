$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Report = Join-Path $Root "PHASE-5-TWIN-CREATE-RUNTIME-DIAGNOSTIC.txt"
$Panel = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Twins = Join-Path $Root "backend\app\api\routes\twins.py"

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Project folder not found: $Root"
}

Set-Location $Root
$Out = New-Object System.Collections.Generic.List[string]

function Section([string]$Title) {
    $Out.Add("")
    $Out.Add("=" * 112)
    $Out.Add($Title)
    $Out.Add("=" * 112)
}

function AddCommandOutput([scriptblock]$Command) {
    try {
        & $Command 2>&1 | ForEach-Object { $Out.Add([string]$_) }
    }
    catch {
        $Out.Add("ERROR: $($_.Exception.Message)")
    }
}

$Out.Add("PETROEDGE AI PHASE 5 TWIN CREATE RUNTIME DIAGNOSTIC")
$Out.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Out.Add("Project: $Root")

Section "DOCKER STATUS"
AddCommandOutput { docker compose ps -a }

Section "BACKEND HEALTH AND ROUTE MODULE STATUS"
try {
    $Health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 30
    $Out.Add(($Health | ConvertTo-Json -Depth 12))
}
catch {
    $Out.Add("HEALTH REQUEST FAILED: $($_.Exception.Message)")
}

Section "OPENAPI DIGITAL TWIN OPERATIONS"
try {
    $OpenApi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 30
    foreach ($Path in @(
        "/api/v1/twins",
        "/api/v1/twins/{reservoir_id}",
        "/api/v1/twin-workspace/{reservoir_id}/summary"
    )) {
        $Property = $OpenApi.paths.PSObject.Properties[$Path]
        if ($null -eq $Property) {
            $Out.Add("MISSING: $Path")
        }
        else {
            $Methods = @($Property.Value.PSObject.Properties.Name) -join ", "
            $Out.Add("$Path -> $Methods")
        }
    }

    $Schema = $OpenApi.components.schemas.TwinCreate
    if ($null -ne $Schema) {
        $Out.Add("")
        $Out.Add("TwinCreate schema:")
        $Out.Add(($Schema | ConvertTo-Json -Depth 12))
    }
    else {
        $Out.Add("TwinCreate schema was not found in OpenAPI.")
    }
}
catch {
    $Out.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

Section "HOST BACKEND ROLE DEFINITIONS"
if (Test-Path -LiteralPath $Twins) {
    Get-Content -LiteralPath $Twins |
        Select-String -Pattern "READ_ROLES|WRITE_ROLES|@router.post|def create_twin" |
        ForEach-Object { $Out.Add("$($_.LineNumber): $($_.Line.Trim())") }
}
else {
    $Out.Add("HOST FILE MISSING: $Twins")
}

Section "ACTIVE BACKEND CONTAINER ROLE DEFINITIONS"
AddCommandOutput {
    docker compose exec -T backend sh -lc `
        'grep -nE "READ_ROLES|WRITE_ROLES|@router.post|def create_twin" /app/app/api/routes/twins.py || true'
}

Section "HOST FRONTEND SOURCE MARKERS"
if (Test-Path -LiteralPath $Panel) {
    foreach ($Pattern in @(
        "fetchAssets",
        "Source asset",
        "No reservoir twin exists yet",
        "twins.isError",
        "createOpen",
        "onClick={() => setCreateOpen(true)}"
    )) {
        $Matches = Select-String -LiteralPath $Panel -Pattern $Pattern -SimpleMatch
        if ($Matches) {
            foreach ($Match in $Matches) {
                $Out.Add("$Pattern -> line $($Match.LineNumber)")
            }
        }
        else {
            $Out.Add("$Pattern -> NOT FOUND")
        }
    }
}
else {
    $Out.Add("HOST FILE MISSING: $Panel")
}

Section "ACTIVE FRONTEND COMPILED BUNDLE MARKERS"
AddCommandOutput {
    docker compose exec -T frontend sh -lc '
      echo "Digital Twin chunks:";
      find /usr/share/nginx/html/assets -maxdepth 1 -type f \( -name "*ReservoirDigitalTwinPanel*.js" -o -name "*DigitalTwin*.js" \) -print;
      echo;
      echo "Marker search:";
      grep -R -l "Source asset" /usr/share/nginx/html/assets 2>/dev/null || true;
      grep -R -l "No reservoir twin exists yet" /usr/share/nginx/html/assets 2>/dev/null || true;
      grep -R -l "Create reservoir twin" /usr/share/nginx/html/assets 2>/dev/null || true
    '
}

Section "FRONTEND INDEX AND CACHE HEADERS"
try {
    $Index = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 30
    $Out.Add("Status: $($Index.StatusCode)")
    foreach ($Header in @("Cache-Control", "ETag", "Last-Modified")) {
        $Out.Add("${Header}: $($Index.Headers[$Header])")
    }
    $Out.Add("")
    $Out.Add("Index asset references:")
    [regex]::Matches($Index.Content, '(?:src|href)="(?<asset>/assets/[^"]+)"') |
        ForEach-Object { $Out.Add($_.Groups["asset"].Value) }
}
catch {
    $Out.Add("FRONTEND INDEX REQUEST FAILED: $($_.Exception.Message)")
}

Section "RECENT BACKEND DIGITAL TWIN REQUESTS AND ERRORS"
AddCommandOutput {
    docker compose logs backend --since 45m --tail 1500 |
        Select-String -Pattern "/api/v1/twins|twin-workspace|403|401|409|422|500|Traceback|ERROR" |
        ForEach-Object { $_.Line }
}

Section "BACKEND SCHEMA AND ORCHESTRATOR SELF-TEST"
AddCommandOutput {
    docker compose exec -T backend python -c @'
from uuid import uuid4
from app.digital_twin import TwinCreate, digital_twin_orchestrator, twin_registry

test_id = "RUNTIME-DIAGNOSTIC-" + uuid4().hex[:8].upper()
request = TwinCreate(reservoir_id=test_id, name="Runtime Diagnostic Twin")
print("TwinCreate:", request.model_dump(mode="json"))
created = digital_twin_orchestrator.create(request)
print("Created:", created.model_dump(mode="json"))
print("Registry count in diagnostic process:", len(twin_registry.list()))
twin_registry.delete(test_id)
print("Deleted diagnostic twin successfully")
'@
}

Section "INTERPRETATION"
$Out.Add("1. If host markers exist but compiled bundle markers do not, the frontend image did not include the patched source.")
$Out.Add("2. If compiled markers exist but the browser still shows the old interface, the browser is serving a cached document or chunk.")
$Out.Add("3. If backend logs show 401 or 403 for /api/v1/twins, authentication or role claims are blocking the request.")
$Out.Add("4. If backend logs show 422, the report will contain the active TwinCreate schema needed to correct the payload.")
$Out.Add("5. If the self-test fails, the backend Digital Twin engine itself is the failing layer.")
$Out.Add("6. The current TwinRegistry is process-memory based, so twins do not survive a backend container restart unless persistence is added.")

$Out | Set-Content -LiteralPath $Report -Encoding utf8

Write-Host ""
Write-Host "DIGITAL TWIN RUNTIME DIAGNOSTIC COMPLETED" -ForegroundColor Green
Write-Host "Report: $Report"
Write-Host ""
Write-Host "Attach PHASE-5-TWIN-CREATE-RUNTIME-DIAGNOSTIC.txt." -ForegroundColor Yellow
