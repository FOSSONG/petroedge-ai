param(
    [string]$OutputRoot = "$env:USERPROFILE\Documents\PetroEdge-Offline-Bundles"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleRoot = Join-Path $OutputRoot "PetroEdge-AI-Offline-$Stamp"

Set-Location $ProjectRoot

foreach ($Image in @(
    "petroedge-release45-backend",
    "petroedge-release45-frontend"
)) {
    docker image inspect $Image *> $null

    if ($LASTEXITCODE -ne 0) {
        throw "Required image missing: $Image"
    }
}

New-Item -ItemType Directory -Path $BundleRoot -Force | Out-Null

Copy-Item ".\docker-compose.yml" $BundleRoot -Force
Copy-Item ".\compose.offline.yml" $BundleRoot -Force

$ImageArchive = Join-Path $BundleRoot "petroedge-images.tar"

docker save `
    -o $ImageArchive `
    petroedge-release45-backend `
    petroedge-release45-frontend

if ($LASTEXITCODE -ne 0) {
    throw "Could not export PetroEdge images."
}

$InstallerLines = @(
    '$ErrorActionPreference = "Stop"',
    'Set-StrictMode -Version Latest',
    '',
    '$BundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path',
    'Set-Location $BundleRoot',
    '',
    'docker info *> $null',
    'if ($LASTEXITCODE -ne 0) {',
    '    throw "Docker Desktop is not ready."',
    '}',
    '',
    'docker load -i ".\petroedge-images.tar"',
    'if ($LASTEXITCODE -ne 0) {',
    '    throw "Could not import PetroEdge images."',
    '}',
    '',
    'docker compose `',
    '    -f ".\docker-compose.yml" `',
    '    -f ".\compose.offline.yml" `',
    '    up -d --no-build --pull never backend frontend',
    '',
    'if ($LASTEXITCODE -ne 0) {',
    '    throw "PetroEdge could not start."',
    '}',
    '',
    '$Deadline = (Get-Date).AddMinutes(3)',
    'while ((Get-Date) -lt $Deadline) {',
    '    try {',
    '        $Response = Invoke-WebRequest `',
    '            -UseBasicParsing `',
    '            -Uri "http://localhost:5173" `',
    '            -TimeoutSec 5',
    '',
    '        if ($Response.StatusCode -eq 200) {',
    '            Start-Process "http://localhost:5173"',
    '            Write-Host "PETROEDGE INSTALLED AND STARTED" -ForegroundColor Green',
    '            exit 0',
    '        }',
    '    }',
    '    catch {',
    '    }',
    '',
    '    Start-Sleep -Seconds 3',
    '}',
    '',
    'throw "PetroEdge frontend did not become ready."'
)

$Installer = $InstallerLines -join [Environment]::NewLine

[System.IO.File]::WriteAllText(
    (Join-Path $BundleRoot "INSTALL-AND-START-PETROEDGE.ps1"),
    $Installer,
    [System.Text.UTF8Encoding]::new($false)
)

$ReadmeLines = @(
    'PETROEDGE AI OFFLINE BUNDLE',
    '',
    'Requirements:',
    '1. Windows 10/11',
    '2. Docker Desktop installed and Engine running',
    '',
    'Install and start:',
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL-AND-START-PETROEDGE.ps1"',
    '',
    'After first installation, PetroEdge can be reopened offline at:',
    'http://localhost:5173'
)

$Readme = $ReadmeLines -join [Environment]::NewLine

[System.IO.File]::WriteAllText(
    (Join-Path $BundleRoot "README.txt"),
    $Readme,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Offline bundle created:" -ForegroundColor Green
Write-Host $BundleRoot -ForegroundColor Green