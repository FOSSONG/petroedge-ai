$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ReportPath = Join-Path $ProjectRoot "PHASE-5-DIGITAL-TWIN-IMPLEMENTATION-INVENTORY.txt"

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
    throw "Project folder not found: $ProjectRoot"
}

Set-Location $ProjectRoot
$Output = New-Object System.Collections.Generic.List[string]

function Add-Section([string]$Title) {
    $Output.Add("")
    $Output.Add("=" * 110)
    $Output.Add($Title)
    $Output.Add("=" * 110)
}

function Add-File([string]$Path, [int]$MaxLines = 420) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Output.Add("FILE NOT FOUND: $Path")
        return
    }
    $Relative = $Path.Substring($ProjectRoot.Length).TrimStart('\')
    $Output.Add("FILE: $Relative")
    $Output.Add("-" * 110)
    $Lines = Get-Content -LiteralPath $Path
    $Limit = [Math]::Min($Lines.Count, $MaxLines)
    for ($i = 0; $i -lt $Limit; $i++) {
        $Output.Add("$($i + 1): $($Lines[$i])")
    }
    if ($Lines.Count -gt $MaxLines) {
        $Output.Add("TRUNCATED: $($Lines.Count) total lines.")
    }
    $Output.Add("")
}

function Add-Search([string]$Root, [string[]]$Patterns) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        $Output.Add("DIRECTORY NOT FOUND: $Root")
        return
    }
    $Files = Get-ChildItem -LiteralPath $Root -Recurse -File |
        Where-Object {
            $_.Extension -in @(".py",".ts",".tsx",".js",".jsx",".json",".yml",".yaml") -and
            $_.FullName -notmatch "\\(node_modules|dist|build|__pycache__|\.pytest_cache|patch-backups)\\"
        }
    foreach ($Pattern in $Patterns) {
        $Output.Add("")
        $Output.Add("PATTERN: $Pattern")
        $Output.Add("-" * 110)
        $Matches = $Files | Select-String -Pattern $Pattern -CaseSensitive:$false
        if (-not $Matches) {
            $Output.Add("NO MATCHES")
        } else {
            foreach ($Match in $Matches) {
                $Relative = $Match.Path.Substring($ProjectRoot.Length).TrimStart('\')
                $Clean = ($Match.Line -replace "\s+"," ").Trim()
                $Output.Add("$Relative`:$($Match.LineNumber): $Clean")
            }
        }
    }
}

$Output.Add("PETROEDGE AI PHASE 5 DIGITAL TWIN IMPLEMENTATION INVENTORY")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("Project: $ProjectRoot")

Add-Section "DOCKER STATUS"
docker compose ps -a 2>&1 | ForEach-Object { $Output.Add([string]$_) }

Add-Section "CURRENT DIGITAL TWIN BACKEND"
Add-File (Join-Path $ProjectRoot "backend\app\api\routes\twins.py") 520

Add-Section "CURRENT DIGITAL REPLAY FRONTEND"
Add-File (Join-Path $ProjectRoot "frontend\src\features\platform\DigitalReplayPanel.tsx") 520

Add-Section "INTERACTIVE LOGS FRONTEND"
Add-File (Join-Path $ProjectRoot "frontend\src\features\platform\WellLogPlotlyPanel.tsx") 520

Add-Section "DASHBOARD REGISTRATION"
Add-File (Join-Path $ProjectRoot "frontend\src\features\dashboard\DashboardPage.tsx") 360

Add-Section "PLUGIN REGISTRY"
Add-File (Join-Path $ProjectRoot "frontend\src\plugins\registry.tsx") 420

Add-Section "FRONTEND PLATFORM API"
Add-File (Join-Path $ProjectRoot "frontend\src\features\platform\platformApi.ts") 620

Add-Section "REFERENCE BACKEND SERVICES"
foreach ($Relative in @(
    "backend\app\api\routes\reservoir_v1.py",
    "backend\app\api\routes\platform.py",
    "backend\app\platform_v1\datasets.py",
    "backend\app\preprocessing\curve_aliases.py"
)) {
    Add-File (Join-Path $ProjectRoot $Relative) 520
}

Add-Section "DIGITAL TWIN REFERENCES"
Add-Search $ProjectRoot @(
    "digital twin|digital_twin|twin",
    "scenario|forecast|simulation",
    "state vector|state update|snapshot",
    "history matching|calibration",
    "pressure|saturation|production",
    "replay|time step|depth step",
    "compare well|comparison well",
    "reservoir model|dynamic model"
)

Add-Section "PLACEHOLDER AND MOCK INDICATORS"
Add-Search (Join-Path $ProjectRoot "frontend\src") @(
    "coming soon",
    "placeholder",
    "mock",
    "demo only",
    "not implemented",
    "capability boundary",
    "connected incrementally",
    "TODO",
    "FIXME"
)

Add-Section "CURRENT OPENAPI TWIN PATHS"
try {
    $OpenApi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -Method Get -TimeoutSec 30
    $Paths = @($OpenApi.paths.PSObject.Properties.Name | Where-Object { $_ -match "twin|replay|scenario|simulation" } | Sort-Object)
    if ($Paths.Count -eq 0) {
        $Output.Add("NO DIGITAL TWIN OR SIMULATION ROUTES CURRENTLY REGISTERED")
    } else {
        $Paths | ForEach-Object { $Output.Add($_) }
    }
} catch {
    $Output.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

Add-Section "IMPLEMENTATION READINESS SUMMARY"
$Output.Add("Recommended first-class workspace target:")
$Output.Add("- Dedicated Reservoir Digital Twin tab")
$Output.Add("- Dataset-linked twin creation")
$Output.Add("- Persisted twin state and scenario history")
$Output.Add("- Baseline reservoir-state snapshot")
$Output.Add("- Transparent pressure, saturation and production scenario controls")
$Output.Add("- Comparison against baseline")
$Output.Add("- Replay timeline and audit history")
$Output.Add("")
$Output.Add("Scientific guardrails:")
$Output.Add("- Label simplified material-balance and decline calculations explicitly")
$Output.Add("- Do not claim full-physics reservoir simulation")
$Output.Add("- Do not fabricate history matching or calibrated forecasts")
$Output.Add("- Preserve CPU-first and lightweight storage architecture")
$Output.Add("- Use registered datasets and existing interpretation outputs where available")

$Output | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host ""
Write-Host "PHASE 5 DIGITAL TWIN IMPLEMENTATION INVENTORY COMPLETED" -ForegroundColor Green
Write-Host "Report created:" -ForegroundColor Cyan
Write-Host $ReportPath
Write-Host ""
Write-Host "No project files were modified." -ForegroundColor Yellow
