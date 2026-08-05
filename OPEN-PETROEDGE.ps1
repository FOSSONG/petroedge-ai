$FrontendUrl = "http://localhost:5173"
try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 5
    if ($Response.StatusCode -eq 200) {
        Start-Process $FrontendUrl
        exit 0
    }
}
catch {
}

$ProjectRoot = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.1.2-DATA-PREPARATION-STUDIO"

powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File (Join-Path $ProjectRoot "START-PETROEDGE.ps1")