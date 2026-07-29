$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Preparing PetroEdge AI MVP..." -ForegroundColor Cyan

Set-Location "$Root\backend"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-windows-dev.txt
& ".\.venv\Scripts\python.exe" -m compileall -q app

Set-Location "$Root\frontend"
if (Test-Path "node_modules") { Remove-Item "node_modules" -Recurse -Force }
npm install
npm run build

Set-Location $Root
Write-Host "PetroEdge AI MVP is ready." -ForegroundColor Green
Write-Host "Local backend: cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload"
Write-Host "Local frontend: cd frontend; npm run dev"
Write-Host "Docker: docker compose up --build"
