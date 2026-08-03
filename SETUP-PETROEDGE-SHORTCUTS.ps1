$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell

$Definitions = @(
    @{
        Name = "Start PetroEdge AI Online"
        Script = "START-PETROEDGE-ONLINE.ps1"
    },
    @{
        Name = "Start PetroEdge AI Offline"
        Script = "START-PETROEDGE-OFFLINE.ps1"
    },
    @{
        Name = "Stop PetroEdge AI"
        Script = "STOP-PETROEDGE.ps1"
    },
    @{
        Name = "Diagnose PetroEdge AI"
        Script = "DIAGNOSE-PETROEDGE.ps1"
    }
)

foreach ($Definition in $Definitions) {
    $Shortcut = $Shell.CreateShortcut(
        (Join-Path $Desktop "$($Definition.Name).lnk")
    )
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = (
        '-NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $ProjectRoot $Definition.Script) +
        '"'
    )
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Save()
}

Write-Host "PetroEdge desktop shortcuts created." -ForegroundColor Green