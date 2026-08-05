$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
Set-Location $ProjectRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not ready."
}

docker compose restart -t 30 backend frontend
if ($LASTEXITCODE -ne 0) {
    throw "PetroEdge could not restart."
}

powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File (Join-Path $ProjectRoot "START-PETROEDGE.ps1")