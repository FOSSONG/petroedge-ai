$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell

$Items = @(
    @{Name="Open PetroEdge AI"; Script="OPEN-PETROEDGE.ps1"},
    @{Name="Start PetroEdge AI"; Script="START-PETROEDGE.ps1"},
    @{Name="Restart PetroEdge AI"; Script="RESTART-PETROEDGE.ps1"},
    @{Name="Stop PetroEdge AI"; Script="STOP-PETROEDGE.ps1"}
)

foreach ($Item in $Items) {
    $Shortcut = $Shell.CreateShortcut(
        (Join-Path $Desktop "$($Item.Name).lnk")
    )
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = (
        '-NoProfile -ExecutionPolicy Bypass -File "' +
        (Join-Path $ProjectRoot $Item.Script) +
        '"'
    )
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Save()
}

Write-Host "PetroEdge shortcuts created." -ForegroundColor Green