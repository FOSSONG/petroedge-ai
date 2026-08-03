$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ReportPath = Join-Path $ProjectRoot "PHASE-2-ASSETS-INVENTORY.txt"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Project folder not found: $ProjectRoot"
}

Set-Location $ProjectRoot

$Output = New-Object System.Collections.Generic.List[string]

function Add-Section {
    param([string]$Title)

    $Output.Add("")
    $Output.Add("=" * 100)
    $Output.Add($Title)
    $Output.Add("=" * 100)
}

function Add-FileContent {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$MaximumLines = 260
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Output.Add("FILE NOT FOUND: $Path")
        return
    }

    $RelativePath = $Path.Substring($ProjectRoot.Length).TrimStart('\')
    $Output.Add("FILE: $RelativePath")
    $Output.Add("-" * 100)

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

$Output.Add("PETROEDGE AI PHASE 2 ASSETS INVENTORY")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("Project: $ProjectRoot")

Add-Section "CURRENT DOCKER STATE"

$ComposePs = & docker compose ps -a 2>&1
foreach ($Line in $ComposePs) {
    $Output.Add([string]$Line)
}

Add-Section "BACKEND MAIN APPLICATION"
Add-FileContent -Path (Join-Path $ProjectRoot "backend\app\main.py") -MaximumLines 320

Add-Section "BACKEND ROUTE FILES"

$RoutesDirectory = Join-Path $ProjectRoot "backend\app\api\routes"

if (Test-Path -LiteralPath $RoutesDirectory -PathType Container) {
    $RouteFiles = Get-ChildItem -LiteralPath $RoutesDirectory -File -Filter "*.py" |
        Sort-Object Name

    foreach ($File in $RouteFiles) {
        $Output.Add($File.Name)
    }
}
else {
    $Output.Add("ROUTES DIRECTORY NOT FOUND: $RoutesDirectory")
}

Add-Section "REFERENCE CRUD ROUTES"

$ReferenceRouteNames = @(
    "wells.py",
    "platform.py",
    "datasets.py",
    "models.py",
    "reports.py"
)

foreach ($Name in $ReferenceRouteNames) {
    Add-FileContent -Path (Join-Path $RoutesDirectory $Name) -MaximumLines 320
}

Add-Section "DATABASE MODELS AND SCHEMAS"

$CandidateFiles = @(
    "backend\app\models.py",
    "backend\app\schemas.py",
    "backend\app\db\models.py",
    "backend\app\db\base.py",
    "backend\app\db\session.py",
    "backend\app\core\config.py"
)

foreach ($RelativePath in $CandidateFiles) {
    Add-FileContent -Path (Join-Path $ProjectRoot $RelativePath) -MaximumLines 320
}

Add-Section "ASSET-RELATED BACKEND REFERENCES"

$BackendRoot = Join-Path $ProjectRoot "backend"

$AssetMatches = Get-ChildItem -LiteralPath $BackendRoot -Recurse -File |
    Where-Object {
        $_.Extension -in @(".py", ".json", ".toml", ".yml", ".yaml") -and
        $_.FullName -notmatch "\\(__pycache__|\.pytest_cache|\.mypy_cache)\\"
    } |
    Select-String -Pattern "asset_id|class Asset|assets|field.*well|well.*field" -CaseSensitive:$false

if ($AssetMatches) {
    foreach ($Match in $AssetMatches) {
        $RelativePath = $Match.Path.Substring($ProjectRoot.Length).TrimStart('\')
        $CleanLine = ($Match.Line -replace "\s+", " ").Trim()
        $Output.Add("$RelativePath`:$($Match.LineNumber): $CleanLine")
    }
}
else {
    $Output.Add("NO ASSET-RELATED BACKEND REFERENCES FOUND")
}

Add-Section "FRONTEND ASSETS API AND UI REFERENCES"

$FrontendRoot = Join-Path $ProjectRoot "frontend\src"

$FrontendMatches = Get-ChildItem -LiteralPath $FrontendRoot -Recurse -File |
    Where-Object {
        $_.Extension -in @(".ts", ".tsx", ".js", ".jsx") -and
        $_.FullName -notmatch "\\(node_modules|dist|build)\\"
    } |
    Select-String -Pattern "fetchAssets|saveAsset|asset_id|Assets|/assets" -CaseSensitive:$false

if ($FrontendMatches) {
    foreach ($Match in $FrontendMatches) {
        $RelativePath = $Match.Path.Substring($ProjectRoot.Length).TrimStart('\')
        $CleanLine = ($Match.Line -replace "\s+", " ").Trim()
        $Output.Add("$RelativePath`:$($Match.LineNumber): $CleanLine")
    }
}
else {
    $Output.Add("NO FRONTEND ASSETS REFERENCES FOUND")
}

Add-Section "CURRENT OPENAPI ASSET PATHS"

try {
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -Method Get `
        -TimeoutSec 20

    $AssetPaths = @(
        $OpenApi.paths.PSObject.Properties.Name |
            Where-Object { $_ -match "asset" } |
            Sort-Object
    )

    if ($AssetPaths.Count -eq 0) {
        $Output.Add("NO ASSET ROUTES CURRENTLY REGISTERED")
    }
    else {
        foreach ($Path in $AssetPaths) {
            $Output.Add($Path)
        }
    }
}
catch {
    $Output.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

$Output | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host ""
Write-Host "PHASE 2 ASSETS INVENTORY COMPLETED" -ForegroundColor Green
Write-Host "Report created:" -ForegroundColor Cyan
Write-Host $ReportPath
Write-Host ""
Write-Host "No project files were modified." -ForegroundColor Yellow
