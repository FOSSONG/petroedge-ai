$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$ReportPath = Join-Path $ProjectRoot "PHASE-1-API-ROUTE-AUDIT.txt"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Project folder not found: $ProjectRoot"
}

Set-Location $ProjectRoot

$ExcludedDirectories = @(
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".next",
    "coverage"
)

$AllowedExtensions = @(
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yml",
    ".yaml",
    ".env",
    ".conf",
    ".toml"
)

function Test-IsExcludedPath {
    param([string]$FullName)

    foreach ($Directory in $ExcludedDirectories) {
        $Marker = [System.IO.Path]::DirectorySeparatorChar + $Directory + [System.IO.Path]::DirectorySeparatorChar
        if ($FullName -like "*$Marker*") {
            return $true
        }
    }

    return $false
}

function Get-RelativePath {
    param([string]$Path)

    return [System.IO.Path]::GetRelativePath($ProjectRoot, $Path)
}

$Files = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File |
    Where-Object {
        -not (Test-IsExcludedPath -FullName $_.FullName) -and
        ($AllowedExtensions -contains $_.Extension.ToLowerInvariant() -or $_.Name -like ".env*")
    }

$Patterns = [ordered]@{
    "Literal duplicated API prefix" = "/api/v1/v1"
    "Version-one router prefix"      = 'prefix\s*=\s*["'']\/v1'
    "Full API router prefix"         = 'prefix\s*=\s*["'']\/api\/v1'
    "FastAPI include_router calls"   = "include_router\s*\("
    "Frontend API base URLs"         = "VITE_API|API_BASE|BASE_URL|localhost:8000|\/api\/v1"
    "Asset route references"         = "\/assets|assets_router|router.*assets"
}

$Output = New-Object System.Collections.Generic.List[string]

$Output.Add("PETROEDGE AI PHASE 1 API ROUTE AUDIT")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("Project: $ProjectRoot")
$Output.Add("=" * 100)

foreach ($Entry in $Patterns.GetEnumerator()) {
    $Output.Add("")
    $Output.Add("SECTION: $($Entry.Key)")
    $Output.Add("-" * 100)

    $MatchesFound = 0

    foreach ($File in $Files) {
        try {
            $Matches = Select-String `
                -LiteralPath $File.FullName `
                -Pattern $Entry.Value `
                -AllMatches `
                -CaseSensitive:$false `
                -ErrorAction Stop

            foreach ($Match in $Matches) {
                $RelativePath = Get-RelativePath -Path $File.FullName
                $CleanLine = ($Match.Line -replace "\s+", " ").Trim()

                $Output.Add(
                    "{0}:{1}: {2}" -f $RelativePath, $Match.LineNumber, $CleanLine
                )

                $MatchesFound++
            }
        }
        catch {
            $Output.Add(
                "READ ERROR: {0}: {1}" -f (Get-RelativePath -Path $File.FullName), $_.Exception.Message
            )
        }
    }

    if ($MatchesFound -eq 0) {
        $Output.Add("NO MATCHES FOUND")
    }
    else {
        $Output.Add("")
        $Output.Add("MATCH COUNT: $MatchesFound")
    }
}

$Output.Add("")
$Output.Add("=" * 100)
$Output.Add("DOCKER COMPOSE CONFIGURATION")
$Output.Add("=" * 100)

$ComposeConfig = & docker compose config 2>&1
$ComposeExitCode = $LASTEXITCODE

foreach ($Line in $ComposeConfig) {
    $Output.Add([string]$Line)
}

$Output.Add("")
$Output.Add("docker compose config exit code: $ComposeExitCode")

$Output.Add("")
$Output.Add("=" * 100)
$Output.Add("RUNNING CONTAINERS")
$Output.Add("=" * 100)

$ComposePs = & docker compose ps -a 2>&1
$ComposePsExitCode = $LASTEXITCODE

foreach ($Line in $ComposePs) {
    $Output.Add([string]$Line)
}

$Output.Add("")
$Output.Add("docker compose ps exit code: $ComposePsExitCode")

$Output.Add("")
$Output.Add("=" * 100)
$Output.Add("OPENAPI ROUTE SNAPSHOT")
$Output.Add("=" * 100)

try {
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -Method Get `
        -TimeoutSec 20

    $Paths = $OpenApi.paths.PSObject.Properties.Name | Sort-Object

    foreach ($Path in $Paths) {
        $Output.Add($Path)
    }

    $Output.Add("")
    $Output.Add("OPENAPI PATH COUNT: $($Paths.Count)")
}
catch {
    $Output.Add("OPENAPI REQUEST FAILED: $($_.Exception.Message)")
}

$Output | Set-Content -LiteralPath $ReportPath -Encoding utf8

Write-Host ""
Write-Host "PHASE 1 API ROUTE AUDIT COMPLETED" -ForegroundColor Green
Write-Host "Report created:" -ForegroundColor Cyan
Write-Host $ReportPath
Write-Host ""
Write-Host "No project files were modified." -ForegroundColor Yellow
