$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Report = Join-Path $ProjectRoot "PETROEDGE-DIAGNOSTIC-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
Set-Location $ProjectRoot

"PETROEDGE AI DIAGNOSTIC REPORT" |
    Set-Content -LiteralPath $Report -Encoding utf8
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')" |
    Add-Content -LiteralPath $Report -Encoding utf8

"`n=== GIT ===" | Add-Content $Report
git status | Add-Content $Report
git log --oneline -5 | Add-Content $Report

"`n=== DOCKER VERSION ===" | Add-Content $Report
docker version 2>&1 | Add-Content $Report

"`n=== COMPOSE CONFIG ===" | Add-Content $Report
docker compose config 2>&1 | Add-Content $Report

"`n=== CONTAINER STATUS ===" | Add-Content $Report
docker compose ps -a 2>&1 | Add-Content $Report

"`n=== MIGRATE LOGS ===" | Add-Content $Report
docker compose logs --timestamps --tail 200 migrate 2>&1 | Add-Content $Report

"`n=== BACKEND LOGS ===" | Add-Content $Report
docker compose logs --timestamps --tail 300 backend 2>&1 | Add-Content $Report

"`n=== FRONTEND LOGS ===" | Add-Content $Report
docker compose logs --timestamps --tail 200 frontend 2>&1 | Add-Content $Report

"`n=== HEALTH ===" | Add-Content $Report
try {
    Invoke-RestMethod "http://localhost:8000/health" |
        ConvertTo-Json -Depth 10 |
        Add-Content $Report
} catch {
    $_.Exception.Message | Add-Content $Report
}

"`n=== READINESS ===" | Add-Content $Report
try {
    Invoke-RestMethod "http://localhost:8000/api/v1/readiness" |
        ConvertTo-Json -Depth 10 |
        Add-Content $Report
} catch {
    $_.Exception.Message | Add-Content $Report
}

"`n=== DIAGNOSTICS ===" | Add-Content $Report
try {
    Invoke-RestMethod "http://localhost:8000/api/v1/diagnostics" |
        ConvertTo-Json -Depth 10 |
        Add-Content $Report
} catch {
    $_.Exception.Message | Add-Content $Report
}

Write-Host "Diagnostic report created:" -ForegroundColor Green
Write-Host $Report -ForegroundColor Yellow