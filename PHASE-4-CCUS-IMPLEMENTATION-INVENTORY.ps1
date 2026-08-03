$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ReportPath = Join-Path $ProjectRoot "PHASE-4-CCUS-IMPLEMENTATION-INVENTORY.txt"

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}

Set-Location $ProjectRoot

$Output = New-Object System.Collections.Generic.List[string]

function Add-Section {
    param([Parameter(Mandatory = $true)][string]$Title)

    $Output.Add("")
    $Output.Add("=" * 110)
    $Output.Add($Title)
    $Output.Add("=" * 110)
}

function Add-FileContent {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$MaximumLines = 360
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Output.Add("FILE NOT FOUND: $Path")
        return
    }

    $RelativePath = $Path.Substring($ProjectRoot.Length).TrimStart('\')
    $Output.Add("FILE: $RelativePath")
    $Output.Add("-" * 110)

    $Lines = Get-Content -LiteralPath $Path -ErrorAction Stop
    $Limit = [Math]::Min($Lines.Count, $MaximumLines)

    for ($Index = 0; $Index -lt $Limit; $Index++) {
        $LineNumber = $Index + 1
        $Output.Add("$LineNumber`: $($Lines[$Index])")
    }

    if ($Lines.Count -gt $MaximumLines) {
        $Output.Add("")
        $Output.Add("TRUNCATED: file contains $($Lines.Count) lines; first $MaximumLines included.")
    }

    $Output.Add("")
}

function Add-Matches {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$Patterns,
        [string[]]$Extensions = @(".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml", ".yml", ".yaml")
    )

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        $Output.Add("DIRECTORY NOT FOUND: $Root")
        return
    }

    $Files = Get-ChildItem -LiteralPath $Root -Recurse -File |
        Where-Object {
            $_.Extension -in $Extensions -and
            $_.FullName -notmatch "\\(node_modules|dist|build|__pycache__|\.pytest_cache|patch-backups)\\"
        }

    foreach ($Pattern in $Patterns) {
        $Output.Add("")
        $Output.Add("PATTERN: $Pattern")
        $Output.Add("-" * 110)

        $Matches = $Files | Select-String -Pattern $Pattern -CaseSensitive:$false

        if (-not $Matches) {
            $Output.Add("NO MATCHES")
            continue
        }

        foreach ($Match in $Matches) {
            $RelativePath = $Match.Path.Substring($ProjectRoot.Length).TrimStart('\')
            $CleanLine = ($Match.Line -replace "\s+", " ").Trim()
            $Output.Add("$RelativePath`:$($Match.LineNumber): $CleanLine")
        }
    }
}

$Output.Add("PETROEDGE AI PHASE 4 CCUS IMPLEMENTATION INVENTORY")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("Project: $ProjectRoot")

Add-Section "DOCKER STATUS"

$ComposeState = docker compose ps -a 2>&1
foreach ($Line in $ComposeState) {
    $Output.Add([string]$Line)
}

Add-Section "CURRENT CCUS FRONTEND"
Add-FileContent `
    -Path (Join-Path $ProjectRoot "frontend\src\features\platform\CcusWorkspacePanel.tsx") `
    -MaximumLines 420

Add-Section "DASHBOARD REGISTRATION AND NAVIGATION"
Add-FileContent `
    -Path (Join-Path $ProjectRoot "frontend\src\features\dashboard\DashboardPage.tsx") `
    -MaximumLines 360

Add-Section "FRONTEND PLATFORM API CONTRACT"
Add-FileContent `
    -Path (Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts") `
    -MaximumLines 420

Add-Section "BACKEND ROUTER REGISTRATION"
Add-FileContent `
    -Path (Join-Path $ProjectRoot "backend\app\main.py") `
    -MaximumLines 320

Add-Section "REFERENCE SCIENTIFIC ROUTES"
$RouteRoot = Join-Path $ProjectRoot "backend\app\api\routes"

foreach ($Name in @("reservoir_v1.py", "platform.py", "edge.py", "analytics.py")) {
    Add-FileContent `
        -Path (Join-Path $RouteRoot $Name) `
        -MaximumLines 420
}

Add-Section "DATASET STORAGE AND PREVIEW IMPLEMENTATION"

foreach ($RelativePath in @(
    "backend\app\platform_v1\datasets.py",
    "backend\app\platform_v1\schemas.py",
    "backend\app\platform_v1\database.py",
    "backend\app\services\analytics.py"
)) {
    Add-FileContent `
        -Path (Join-Path $ProjectRoot $RelativePath) `
        -MaximumLines 420
}

Add-Section "CCUS AND STORAGE-CAPACITY REFERENCES"

Add-Matches `
    -Root $ProjectRoot `
    -Patterns @(
        "CCUS|CCS|carbon capture|carbon storage",
        "storage capacity|capacity estimate|injectivity",
        "containment|seal integrity|caprock",
        "CO2 density|CO₂ density|formation volume factor",
        "saline aquifer|depleted reservoir",
        "pressure limit|fracture pressure",
        "porosity|permeability|net thickness|area",
        "sweep efficiency|storage efficiency"
    )

Add-Section "AVAILABLE DATASET METADATA FIELDS"

Add-Matches `
    -Root (Join-Path $ProjectRoot "backend") `
    -Patterns @(
        "field_name",
        "well_name",
        "reservoir_name",
        "dataset_type",
        "columns",
        "units",
        "row_count",
        "min_depth",
        "max_depth",
        "metadata_json"
    ) `
    -Extensions @(".py", ".json")

Add-Section "CURRENT OPENAPI CCUS PATHS"

try {
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -Method Get `
        -TimeoutSec 30

    $Paths = @(
        $OpenApi.paths.PSObject.Properties.Name |
            Where-Object { $_ -match "ccus|carbon|storage|inject" } |
            Sort-Object
    )

    if ($Paths.Count -eq 0) {
        $Output.Add("NO CCUS ROUTES CURRENTLY REGISTERED")
    }
    else {
        foreach ($Path in $Paths) {
            $Output.Add($Path)
        }
    }
}
catch {
    $Output.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

Add-Section "IMPLEMENTATION READINESS SUMMARY"

$FrontendFile = Join-Path $ProjectRoot "frontend\src\features\platform\CcusWorkspacePanel.tsx"
$PlatformApiFile = Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts"

$FrontendExists = Test-Path -LiteralPath $FrontendFile -PathType Leaf
$PlatformApiExists = Test-Path -LiteralPath $PlatformApiFile -PathType Leaf

$Output.Add("CCUS frontend exists: $FrontendExists")
$Output.Add("Platform API file exists: $PlatformApiExists")
$Output.Add("Backend CCUS route registered: False unless listed above")
$Output.Add("Recommended implementation target:")
$Output.Add("- GET /api/v1/ccus/capabilities")
$Output.Add("- POST /api/v1/ccus/screen")
$Output.Add("- GET /api/v1/ccus/runs")
$Output.Add("- GET /api/v1/ccus/runs/{run_id}")
$Output.Add("- DELETE /api/v1/ccus/runs/{run_id}")
$Output.Add("")
$Output.Add("Scientific MVP scope:")
$Output.Add("- Volumetric CO2 storage capacity screening")
$Output.Add("- Reservoir suitability scoring")
$Output.Add("- Injectivity proxy")
$Output.Add("- Containment and data-quality risk flags")
$Output.Add("- Persistent, auditable screening runs")
$Output.Add("- No fabricated plume simulation or geomechanical forecast")

$Output | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host ""
Write-Host "PHASE 4 CCUS IMPLEMENTATION INVENTORY COMPLETED" -ForegroundColor Green
Write-Host "Report created:" -ForegroundColor Cyan
Write-Host $ReportPath
Write-Host ""
Write-Host "No project files were modified." -ForegroundColor Yellow
