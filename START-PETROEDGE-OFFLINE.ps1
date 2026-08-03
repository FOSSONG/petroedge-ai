$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendUrl = "http://localhost:5173"

Set-Location $ProjectRoot

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not ready. Start Docker Desktop and wait for Engine running."
}

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "The PetroEdge Docker Compose configuration is invalid."
}

$Containers = @(docker compose ps -a --services --filter "status=running")
if ($Containers.Count -lt 2) {
    docker compose up -d --no-build
    if ($LASTEXITCODE -ne 0) {
        throw "PetroEdge could not start from local Docker images. A one-time online build may be required."
    }
}

$Deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $Deadline) {
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 5
        if ($Response.StatusCode -eq 200) {
            Start-Process $FrontendUrl
            exit 0
        }
    } catch {}
    Start-Sleep -Seconds 3
}

throw "PetroEdge containers started, but the frontend did not become ready."
