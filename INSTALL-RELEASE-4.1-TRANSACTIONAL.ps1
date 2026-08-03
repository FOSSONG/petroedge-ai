$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Parent = Split-Path -Parent $Source
$ProjectName = Split-Path -Leaf $Source
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Backup = Join-Path $Parent "$ProjectName-backup-$Timestamp"
$Report = Join-Path $Source 'RELEASE-4.1-INSTALL-REPORT.txt'

function Log([string]$Message) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $line -ForegroundColor Cyan
    Add-Content -Path $Report -Value $line
}

Remove-Item $Report -Force -ErrorAction SilentlyContinue
Log 'Transactional Release 4.1 deployment started.'

try {
    Log "Creating verified source snapshot at $Backup"
    Copy-Item -Path $Source -Destination $Backup -Recurse -Force
    $sourceCount = (Get-ChildItem $Source -Recurse -File | Measure-Object).Count
    $backupCount = (Get-ChildItem $Backup -Recurse -File | Measure-Object).Count
    if ($sourceCount -ne $backupCount) {
        throw "Snapshot verification failed: source=$sourceCount backup=$backupCount"
    }

    Log 'Running Docker-based validation.'
    & (Join-Path $Source 'VALIDATE-RELEASE-4.1.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Release validation returned a non-zero exit code.' }

    Log 'Deployment completed successfully.'
    Write-Host "Backup retained at: $Backup" -ForegroundColor Green
}
catch {
    Log "Deployment failed: $($_.Exception.Message)"
    Log 'Stopping failed containers and restoring the verified snapshot.'
    Push-Location $Source
    try { docker compose down --remove-orphans } catch { }
    Pop-Location

    $Failed = "$Source-failed-$Timestamp"
    Move-Item -Path $Source -Destination $Failed -Force
    Copy-Item -Path $Backup -Destination $Source -Recurse -Force
    Log "Rollback completed. Failed tree retained at $Failed"
    Write-Host 'Release 4.1 failed and the previous project state was restored.' -ForegroundColor Red
    exit 1
}
