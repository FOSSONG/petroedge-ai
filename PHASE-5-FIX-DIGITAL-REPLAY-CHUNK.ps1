$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Result = Join-Path $Root "PHASE-5-DIGITAL-REPLAY-CHUNK-FIX-RESULT.txt"

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Project folder not found: $Root"
}

Set-Location $Root

Write-Host "[1/5] Validating Docker Compose..." -ForegroundColor Cyan
docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "[2/5] Removing the current frontend container..." -ForegroundColor Cyan
docker compose rm -sf frontend
if ($LASTEXITCODE -ne 0) {
    throw "Could not remove the frontend container."
}

Write-Host "[3/5] Rebuilding the frontend without cache..." -ForegroundColor Cyan
docker compose build --no-cache frontend
if ($LASTEXITCODE -ne 0) {
    throw "Frontend no-cache build failed."
}

Write-Host "[4/5] Recreating the frontend service..." -ForegroundColor Cyan
docker compose up -d --force-recreate frontend
if ($LASTEXITCODE -ne 0) {
    throw "Frontend recreation failed."
}

Start-Sleep -Seconds 5

Write-Host "[5/5] Verifying generated frontend assets..." -ForegroundColor Cyan

$IndexResponse = Invoke-WebRequest `
    -Uri "http://localhost:5173/" `
    -UseBasicParsing `
    -TimeoutSec 30

if ($IndexResponse.StatusCode -ne 200) {
    throw "Frontend index returned HTTP $($IndexResponse.StatusCode)."
}

$IndexHtml = $IndexResponse.Content
$AssetMatches = [regex]::Matches(
    $IndexHtml,
    '(?:src|href)="(?<path>/assets/[^"]+)"'
)

$Assets = @(
    $AssetMatches |
        ForEach-Object { $_.Groups["path"].Value } |
        Sort-Object -Unique
)

$Missing = New-Object System.Collections.Generic.List[string]

foreach ($Asset in $Assets) {
    try {
        $Response = Invoke-WebRequest `
            -Uri ("http://localhost:5173" + $Asset) `
            -Method Head `
            -UseBasicParsing `
            -TimeoutSec 20

        if ($Response.StatusCode -ne 200) {
            $Missing.Add("$Asset -> HTTP $($Response.StatusCode)")
        }
    }
    catch {
        $Missing.Add("$Asset -> $($_.Exception.Message)")
    }
}

$ReplayReferences = docker compose exec -T frontend sh -lc `
    'find /usr/share/nginx/html/assets -maxdepth 1 -type f -name "DigitalReplayPanel-*.js" -print' 2>&1

$Output = New-Object System.Collections.Generic.List[string]
$Output.Add("PETROEDGE AI DIGITAL REPLAY CHUNK FIX RESULT")
$Output.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')")
$Output.Add("")
$Output.Add("Frontend index status: $($IndexResponse.StatusCode)")
$Output.Add("Indexed root assets: $($Assets.Count)")
$Output.Add("Missing indexed assets: $($Missing.Count)")
$Output.Add("")
$Output.Add("Digital Replay chunks in active frontend container:")

foreach ($Line in $ReplayReferences) {
    $Output.Add([string]$Line)
}

if ($Missing.Count -gt 0) {
    $Output.Add("")
    $Output.Add("Missing assets:")
    foreach ($Item in $Missing) {
        $Output.Add($Item)
    }
}

$Output.Add("")
$Output.Add("Docker state:")
docker compose ps -a 2>&1 | ForEach-Object { $Output.Add([string]$_) }

$Output | Set-Content -LiteralPath $Result -Encoding utf8

if ($Missing.Count -gt 0) {
    throw "Some assets are still missing. Review: $Result"
}

Write-Host ""
Write-Host "DIGITAL REPLAY FRONTEND CHUNK FIX COMPLETED" -ForegroundColor Green
Write-Host "Result: $Result"
Write-Host ""
Write-Host "In the browser, close all PetroEdge tabs, reopen http://localhost:5173, and press Ctrl+Shift+R." -ForegroundColor Yellow
