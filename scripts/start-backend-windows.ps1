param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

Set-Location $Backend

if (-not (Test-Path $Python)) {
  py -3.11 -m venv .venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-windows-dev.txt
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload

