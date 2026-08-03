$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Panel = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root "patch-backups\phase5-twin-auth-ready-$Stamp"
$Result = Join-Path $Root "PHASE-5-TWIN-AUTH-READY-RESULT.txt"

if (-not (Test-Path -LiteralPath $Panel -PathType Leaf)) {
    throw "Required file not found: $Panel"
}

New-Item -ItemType Directory -Path $Backup -Force | Out-Null
Copy-Item -LiteralPath $Panel -Destination (Join-Path $Backup "ReservoirDigitalTwinPanel.tsx") -Force

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$Content = [System.IO.File]::ReadAllText($Panel)

Write-Host "[1/5] Adding a shared authentication-recovery policy..." -ForegroundColor Cyan

$HelperAnchor = 'const numericPaths='
$Policy = @'
const isAuthStartupError=(error:unknown)=>error instanceof Error&&/(401|unauthori[sz]ed|token|authentication|not authenticated)/i.test(error.message);
const authRecoveryQuery={
 retry:(failureCount:number,error:unknown)=>failureCount<12&&isAuthStartupError(error),
 retryDelay:(attempt:number)=>Math.min(500+(attempt*350),2500),
 refetchOnMount:"always" as const,
 refetchOnReconnect:true,
 refetchOnWindowFocus:true,
 staleTime:0
};
'@

if (-not $Content.Contains('const authRecoveryQuery=')) {
    $Index = $Content.IndexOf($HelperAnchor)
    if ($Index -lt 0) {
        throw "Could not locate the Digital Twin helper section."
    }
    $Content = $Content.Insert($Index, $Policy)
}

Write-Host "[2/5] Applying recovery to Twins, Datasets and Assets..." -ForegroundColor Cyan

$Content = [regex]::Replace(
    $Content,
    'const twins=useQuery\(\{[\s\S]*?queryKey:\["twins"\][\s\S]*?\}\);',
    'const twins=useQuery({queryKey:["twins"],queryFn:fetchTwins,...authRecoveryQuery});',
    1
)

$Content = [regex]::Replace(
    $Content,
    'const datasets=useQuery\(\{queryKey:\["platform","datasets"\],queryFn:fetchDatasets(?:,[^}]*)?\}\);',
    'const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets,...authRecoveryQuery});',
    1
)

$Content = [regex]::Replace(
    $Content,
    'const assets=useQuery\(\{queryKey:\["assets"\],queryFn:fetchAssets(?:,[^}]*)?\}\);',
    'const assets=useQuery({queryKey:["assets"],queryFn:fetchAssets,...authRecoveryQuery});',
    1
)

foreach ($Required in @(
    'const twins=useQuery({queryKey:["twins"],queryFn:fetchTwins,...authRecoveryQuery});',
    'const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets,...authRecoveryQuery});',
    'const assets=useQuery({queryKey:["assets"],queryFn:fetchAssets,...authRecoveryQuery});'
)) {
    if (-not $Content.Contains($Required)) {
        throw "Failed to apply query recovery: $Required"
    }
}

Write-Host "[3/5] Adding an authentication-readiness polling fallback..." -ForegroundColor Cyan

$ComponentMarker = ' const [selected,setSelected]=useState("");'
$PollingEffect = @'
 const authRecoveryAttempts=useRef(0);
 useEffect(()=>{
  const timer=window.setInterval(()=>{
   const unresolved=twins.isError||datasets.isError||assets.isError||(!twins.data&&!twins.isFetching);
   if(!unresolved||authRecoveryAttempts.current>=12){window.clearInterval(timer);return}
   authRecoveryAttempts.current+=1;
   void Promise.allSettled([twins.refetch(),datasets.refetch(),assets.refetch()]);
  },750);
  return()=>window.clearInterval(timer);
 },[twins.isError,datasets.isError,assets.isError,twins.data,twins.isFetching]);
'@

if (-not $Content.Contains('const authRecoveryAttempts=useRef(0);')) {
    if (-not $Content.Contains($ComponentMarker)) {
        throw "Could not locate component state anchor."
    }
    $Content = $Content.Replace($ComponentMarker, $PollingEffect + "`r`n" + $ComponentMarker)
}

if ($Content.Contains('useEffect,useMemo,useState')) {
    $Content = $Content.Replace(
        'useEffect,useMemo,useState',
        'useEffect,useMemo,useRef,useState'
    )
}
elseif (-not $Content.Contains('useRef')) {
    throw "React import could not be updated with useRef."
}

Write-Host "[4/5] Improving disabled-state feedback..." -ForegroundColor Cyan

$CreateButtonPattern = '<Button variant="contained" onClick=\{\(\)=>create\.mutate\(\)\} disabled=\{([^}]*)\}>Create</Button>'
$CreateButtonReplacement = '<Button variant="contained" onClick={()=>create.mutate()} disabled={!reservoirId.trim()||!name.trim()||create.isPending}>{create.isPending?"Creating…":"Create"}</Button>'
$Content = [regex]::Replace($Content, $CreateButtonPattern, $CreateButtonReplacement, 1)

$DialogStack = '<DialogContent><Stack spacing={2} mt={1}>'
$ReadinessAlert = @'
<DialogContent><Stack spacing={2} mt={1}>
{(twins.isFetching||datasets.isFetching||assets.isFetching)&&<Alert severity="info">Connecting the Digital Twin workspace to authenticated Assets and Datasets…</Alert>}
'@.TrimEnd()

if ($Content.Contains($DialogStack) -and -not $Content.Contains('Connecting the Digital Twin workspace to authenticated Assets and Datasets')) {
    $Content = $Content.Replace($DialogStack, $ReadinessAlert)
}

Write-Utf8NoBom -Path $Panel -Content $Content

Write-Host "[5/5] Rebuilding the active frontend without cache..." -ForegroundColor Cyan
Set-Location $Root

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed. Backup: $Backup"
}

docker compose rm -sf frontend
docker compose build --no-cache frontend
if ($LASTEXITCODE -ne 0) {
    throw "Frontend build failed. Backup: $Backup"
}

docker compose up -d --force-recreate frontend
if ($LASTEXITCODE -ne 0) {
    throw "Frontend recreation failed. Backup: $Backup"
}

Start-Sleep -Seconds 5

$Index = Invoke-WebRequest -Uri "http://localhost:5173/" -UseBasicParsing -TimeoutSec 30
$Marker = docker compose exec -T frontend sh -lc `
    "grep -R -l 'Connecting the Digital Twin workspace to authenticated Assets and Datasets' /usr/share/nginx/html/assets 2>/dev/null || true" 2>&1

@(
    "PETROEDGE AI PHASE 5 TWIN AUTH-READY RESULT"
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
    "Backup: $Backup"
    "Frontend HTTP status: $($Index.StatusCode)"
    ""
    "Compiled recovery marker:"
    $Marker
    ""
    "$(docker compose ps -a | Out-String)"
) | Set-Content -LiteralPath $Result -Encoding utf8

Write-Host ""
Write-Host "DIGITAL TWIN AUTHENTICATION-READINESS FIX COMPLETED" -ForegroundColor Green
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
Write-Host "Close every PetroEdge tab, reopen http://localhost:5173, and press Ctrl+Shift+R once." -ForegroundColor Yellow
