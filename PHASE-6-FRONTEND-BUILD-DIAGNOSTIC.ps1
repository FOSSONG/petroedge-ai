$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Report = Join-Path $Root "PHASE-6-FRONTEND-BUILD-DIAGNOSTIC.txt"

Set-Location $Root

@(
    "PETROEDGE AI PHASE 6 FRONTEND BUILD DIAGNOSTIC"
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
    "Project: $Root"
    ""
    "The previous implementation rolled back successfully."
    "This diagnostic captures the full frontend compiler output."
    ""
) | Set-Content -LiteralPath $Report -Encoding utf8

Write-Host "Capturing full frontend build output..." -ForegroundColor Cyan

$env:BUILDKIT_PROGRESS = "plain"

docker compose build --no-cache --progress=plain frontend *>&1 |
    Tee-Object -FilePath $Report -Append

$ExitCode = $LASTEXITCODE

@(
    ""
    "===================================================================================================="
    "BUILD EXIT CODE"
    "===================================================================================================="
    "$ExitCode"
    ""
    "===================================================================================================="
    "FILTERED TYPESCRIPT / VITE ERRORS"
    "===================================================================================================="
) | Add-Content -LiteralPath $Report -Encoding utf8

$Patterns = @(
    "error TS",
    "TS[0-9][0-9][0-9][0-9]",
    "Could not resolve",
    "Cannot find module",
    "is declared but its value is never read",
    "Property .* does not exist",
    "Type .* is not assignable",
    "Expected .* arguments",
    "Unexpected token",
    "failed to load config",
    "Build failed"
)

$Lines = Get-Content -LiteralPath $Report
$Matches = foreach ($Pattern in $Patterns) {
    $Lines | Select-String -Pattern $Pattern -CaseSensitive:$false
}

if ($Matches) {
    $Matches |
        Sort-Object LineNumber -Unique |
        ForEach-Object { "Line $($_.LineNumber): $($_.Line)" } |
        Add-Content -LiteralPath $Report -Encoding utf8
}
else {
    "No filtered compiler line was detected. Review the complete output above." |
        Add-Content -LiteralPath $Report -Encoding utf8
}

Write-Host ""
Write-Host "Diagnostic completed." -ForegroundColor Green
Write-Host "Report: $Report" -ForegroundColor Yellow
Write-Host "Please upload PHASE-6-FRONTEND-BUILD-DIAGNOSTIC.txt." -ForegroundColor Yellow

exit 0
