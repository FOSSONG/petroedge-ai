param(
  [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Frontend = Join-Path $Root "frontend"

Set-Location $Frontend

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found. Install Node.js LTS from https://nodejs.org, then reopen PowerShell."
}

if (-not (Test-Path "node_modules")) {
  npm install
}

npm run dev -- --host 127.0.0.1 --port $Port

