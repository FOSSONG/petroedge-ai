$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ReportPath = Join-Path $ProjectRoot "PHASE-3-WORKSPACE-INTEGRATION-AUDIT.txt"

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

function Add-Matches {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$Patterns,
        [string[]]$Extensions = @(".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".yml", ".yaml")
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

$Output.Add("PETROEDGE AI PHASE 3 WORKSPACE INTEGRATION AUDIT")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("Project: $ProjectRoot")

Add-Section "DOCKER STATUS"

$ComposeState = docker compose ps -a 2>&1
foreach ($Line in $ComposeState) {
    $Output.Add([string]$Line)
}

Add-Section "FRONTEND ROUTING AND NAVIGATION"

Add-Matches `
    -Root (Join-Path $ProjectRoot "frontend\src") `
    -Patterns @(
        "createBrowserRouter|BrowserRouter|Routes|Route",
        "nav|navigation|sidebar|menu",
        "workspace|tab|module",
        "path:",
        "label:",
        "title:"
    ) `
    -Extensions @(".ts", ".tsx", ".js", ".jsx")

Add-Section "TARGET WORKSPACE REFERENCES"

Add-Matches `
    -Root (Join-Path $ProjectRoot "frontend\src") `
    -Patterns @(
        "Edge Computing|edge",
        "Assets|asset",
        "Reservoir Intelligence|reservoir",
        "Digital Twin|twin",
        "Workflow|workflow",
        "Multi-Agent|agent",
        "Streaming|realtime|telemetry",
        "Reports|report",
        "Model Registry|models",
        "Dataset|data platform|platform"
    ) `
    -Extensions @(".ts", ".tsx", ".js", ".jsx")

Add-Section "PLACEHOLDER AND STUB INDICATORS"

Add-Matches `
    -Root (Join-Path $ProjectRoot "frontend\src") `
    -Patterns @(
        "coming soon",
        "placeholder",
        "not implemented",
        "mock",
        "demo only",
        "TODO",
        "FIXME",
        "disabled",
        "stub"
    ) `
    -Extensions @(".ts", ".tsx", ".js", ".jsx")

Add-Section "FRONTEND API CALLS"

Add-Matches `
    -Root (Join-Path $ProjectRoot "frontend\src") `
    -Patterns @(
        "apiRequest",
        "fetch\(",
        "axios",
        "VITE_API_BASE_URL",
        "VITE_WS_BASE_URL",
        "/api/v1",
        "WebSocket"
    ) `
    -Extensions @(".ts", ".tsx", ".js", ".jsx")

Add-Section "BACKEND ROUTE REGISTRATION"

$MainFile = Join-Path $ProjectRoot "backend\app\main.py"

if (Test-Path -LiteralPath $MainFile -PathType Leaf) {
    $Lines = Get-Content -LiteralPath $MainFile

    for ($Index = 0; $Index -lt $Lines.Count; $Index++) {
        if (
            $Lines[$Index] -match "ROUTE_MODULES|include_router|API_PREFIX|full_prefix" -or
            $Lines[$Index] -match '\("[A-Za-z0-9_]+",\s*"'
        ) {
            $LineNumber = $Index + 1
            $Output.Add("backend\app\main.py`:$LineNumber`: $($Lines[$Index].Trim())")
        }
    }
}
else {
    $Output.Add("FILE NOT FOUND: backend\app\main.py")
}

Add-Section "OPENAPI ROUTE SNAPSHOT"

try {
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -Method Get `
        -TimeoutSec 30

    $Paths = @($OpenApi.paths.PSObject.Properties.Name | Sort-Object)

    foreach ($Path in $Paths) {
        $Output.Add($Path)
    }

    $Output.Add("")
    $Output.Add("OPENAPI PATH COUNT: $($Paths.Count)")
}
catch {
    $Output.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

Add-Section "WORKSPACE/API COVERAGE SUMMARY"

$WorkspaceDefinitions = @(
    @{ Name = "Assets"; Frontend = "asset"; Api = "/api/v1/assets" },
    @{ Name = "Edge Computing"; Frontend = "edge"; Api = "/api/v1/edge" },
    @{ Name = "Reservoir Intelligence"; Frontend = "reservoir"; Api = "/api/v1/datasets" },
    @{ Name = "Digital Twin"; Frontend = "twin"; Api = "/api/v1/twins" },
    @{ Name = "Workflow Engine"; Frontend = "workflow"; Api = "/api/v1/workflows" },
    @{ Name = "Multi-Agent AI"; Frontend = "agent"; Api = "/api/v1/agents" },
    @{ Name = "Streaming"; Frontend = "stream|realtime|telemetry"; Api = "/api/v1/streaming" },
    @{ Name = "Reports"; Frontend = "report"; Api = "/api/v1/reports" },
    @{ Name = "Models"; Frontend = "model"; Api = "/api/v1/models" },
    @{ Name = "Data Platform"; Frontend = "dataset|platform"; Api = "/api/v1/platform" }
)

$FrontendFiles = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "frontend\src") -Recurse -File |
    Where-Object {
        $_.Extension -in @(".ts", ".tsx", ".js", ".jsx") -and
        $_.FullName -notmatch "\\(node_modules|dist|build)\\"
    }

$KnownPaths = @()

try {
    if ($OpenApi) {
        $KnownPaths = @($OpenApi.paths.PSObject.Properties.Name)
    }
}
catch {
    $KnownPaths = @()
}

foreach ($Workspace in $WorkspaceDefinitions) {
    $FrontendFound = $false

    foreach ($File in $FrontendFiles) {
        if (Select-String -LiteralPath $File.FullName -Pattern $Workspace.Frontend -CaseSensitive:$false -Quiet) {
            $FrontendFound = $true
            break
        }
    }

    $ApiFound = @($KnownPaths | Where-Object { $_ -like "$($Workspace.Api)*" }).Count -gt 0

    $Output.Add(
        "$($Workspace.Name): frontend_reference=$FrontendFound; backend_route=$ApiFound; api_prefix=$($Workspace.Api)"
    )
}

$Output | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host ""
Write-Host "PHASE 3 WORKSPACE INTEGRATION AUDIT COMPLETED" -ForegroundColor Green
Write-Host "Report created:" -ForegroundColor Cyan
Write-Host $ReportPath
Write-Host ""
Write-Host "No project files were modified." -ForegroundColor Yellow
