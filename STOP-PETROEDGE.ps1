$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
Set-Location $ProjectRoot

docker compose stop -t 30 frontend backend
if ($LASTEXITCODE -ne 0) {
    throw "PetroEdge could not be stopped cleanly."
}

docker compose ps -a
Write-Host "PetroEdge stopped. Data and images were preserved." -ForegroundColor Green