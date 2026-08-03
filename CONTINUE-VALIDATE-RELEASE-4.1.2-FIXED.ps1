$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$Report = Join-Path $ProjectRoot "RELEASE-4.1.2-VALIDATION-REPORT-FIXED.txt"

Set-Location $ProjectRoot

function Write-Report {
    param([string]$Message)
    $Line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $Line
    Add-Content -LiteralPath $Report -Value $Line -Encoding utf8
}

function Wait-Backend {
    param([int]$TimeoutSeconds = 180)

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $LastError = ""

    while ((Get-Date) -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest `
                -UseBasicParsing `
                -Uri "http://localhost:8000/health" `
                -TimeoutSec 8

            if ($Response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            $LastError = $_.Exception.Message
        }

        Start-Sleep -Seconds 3
    }

    throw "Backend did not become healthy. Last error: $LastError"
}

"PETROEDGE AI RELEASE 4.1.2 FIXED VALIDATION" |
    Set-Content -LiteralPath $Report -Encoding utf8

try {
    Write-Report "Validating Docker Compose configuration."
    docker compose config --quiet

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose configuration validation failed."
    }

    Write-Report "Stopping any existing services from this Compose project."
    docker compose down --remove-orphans

    Write-Report "Removing only conflicting PetroEdge containers that exist."
    foreach ($ContainerName in @(
        "petroedge-mvp-backend",
        "petroedge-mvp-frontend"
    )) {
        $Existing = docker ps -a `
            --filter "name=^/$ContainerName$" `
            --format "{{.Names}}"

        if ($Existing -eq $ContainerName) {
            docker rm -f $ContainerName | Out-Null

            if ($LASTEXITCODE -ne 0) {
                throw "Failed to remove existing container: $ContainerName"
            }

            Write-Report "Removed existing container: $ContainerName"
        }
        else {
            Write-Report "Container not present, nothing to remove: $ContainerName"
        }
    }

    Write-Report "Starting the images that were already built."
    docker compose up -d --no-build

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed to start Release 4.1.2."
    }

    Write-Report "Waiting for actual backend health."
    Wait-Backend -TimeoutSeconds 180
    Write-Report "Backend health check passed."

    Write-Report "Checking frontend availability."
    $Frontend = Invoke-WebRequest `
        -UseBasicParsing `
        -Uri "http://localhost:5173/" `
        -TimeoutSec 20

    if ($Frontend.StatusCode -ne 200) {
        throw "Frontend returned HTTP $($Frontend.StatusCode)."
    }

    Write-Report "Frontend availability check passed."

    Write-Report "Verifying Release 4.1.2 OpenAPI routes."
    $OpenApi = Invoke-RestMethod `
        -Uri "http://localhost:8000/openapi.json" `
        -TimeoutSec 30

    $RequiredRoutes = @(
        "/api/v1/platform/datasets/{dataset_id}/quality",
        "/api/v1/platform/datasets/{dataset_id}/prepare",
        "/api/v1/platform/datasets/{dataset_id}/edit",
        "/api/v1/platform/datasets/{dataset_id}/download",
        "/api/v1/training-lifecycle/predictions/{output_name}/download"
    )

    foreach ($Route in $RequiredRoutes) {
        if ($OpenApi.paths.PSObject.Properties.Name -notcontains $Route) {
            throw "Missing OpenAPI route: $Route"
        }

        Write-Report "Route verified: $Route"
    }

    Write-Report "Displaying final container status."
    docker compose ps -a | Tee-Object -FilePath $Report -Append

    Write-Report "Release 4.1.2 validation passed."
    Write-Host ""
    Write-Host "SUCCESS: PetroEdge AI Release 4.1.2 is running." -ForegroundColor Green
    Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
    Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Report:   $Report" -ForegroundColor DarkGray
}
catch {
    Write-Report "Validation failed: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "Container status:" -ForegroundColor Yellow
    docker compose ps -a | Out-Host
    Write-Host ""
    Write-Host "Recent backend logs:" -ForegroundColor Yellow
    docker compose logs backend --tail 200 | Out-Host
    throw
}
