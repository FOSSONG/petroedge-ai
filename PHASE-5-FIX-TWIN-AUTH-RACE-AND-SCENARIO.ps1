$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Panel = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root "patch-backups\phase5-twin-runtime-stability-$Stamp"
$Result = Join-Path $Root "PHASE-5-TWIN-RUNTIME-STABILITY-RESULT.txt"

if (-not (Test-Path -LiteralPath $Panel -PathType Leaf)) {
    throw "Digital Twin panel not found: $Panel"
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

Write-Host "[1/5] Stabilising authenticated Digital Twin loading..." -ForegroundColor Cyan

$OldTwinsQuery = ' const twins=useQuery({queryKey:["twins"],queryFn:fetchTwins});'
$NewTwinsQuery = @'
 const twins=useQuery({
  queryKey:["twins"],
  queryFn:fetchTwins,
  retry:(failureCount,error)=>failureCount<5&&error instanceof Error&&/(401|unauthori[sz]ed|token|authentication)/i.test(error.message),
  retryDelay:attempt=>Math.min(750*(attempt+1),3000),
  refetchOnWindowFocus:true
 });
'@.TrimEnd()

if ($Content.Contains($OldTwinsQuery)) {
    $Content = $Content.Replace($OldTwinsQuery, $NewTwinsQuery)
}
elseif (-not $Content.Contains('retryDelay:attempt=>Math.min(750*(attempt+1),3000)')) {
    throw "Twin query anchor was not found."
}

Write-Host "[2/5] Preventing empty-ID requests..." -ForegroundColor Cyan

$OldRefresh = ' const refresh=async()=>{await Promise.all([twins.refetch(),summary.refetch(),history.refetch()])};'
$NewRefresh = ' const refresh=async()=>{const jobs:Promise<unknown>[]=[twins.refetch()];if(id){jobs.push(summary.refetch(),history.refetch())}await Promise.all(jobs)};'

if ($Content.Contains($OldRefresh)) {
    $Content = $Content.Replace($OldRefresh, $NewRefresh)
}

Write-Host "[3/5] Making scenario paths state-aware..." -ForegroundColor Cyan

$OldHelpers = @'
const entries=(value:unknown)=>value&&typeof value==="object"&&!Array.isArray(value)?Object.entries(value as Record<string,unknown>):[];
const label=(value:string)=>value.replace(/_/g," ");
const display=(value:unknown)=>typeof value==="number"?value.toLocaleString(undefined,{maximumFractionDigits:4}):typeof value==="boolean"?(value?"Yes":"No"):String(value??"—");
'@.TrimEnd()

$NewHelpers = @'
const entries=(value:unknown)=>value&&typeof value==="object"&&!Array.isArray(value)?Object.entries(value as Record<string,unknown>):[];
const label=(value:string)=>value.replace(/_/g," ");
const display=(value:unknown)=>typeof value==="number"?value.toLocaleString(undefined,{maximumFractionDigits:4}):typeof value==="boolean"?(value?"Yes":"No"):String(value??"—");
const numericPaths=(value:unknown,prefix=""):string[]=>{
 if(!value||typeof value!=="object"||Array.isArray(value))return [];
 return Object.entries(value as Record<string,unknown>).flatMap(([key,item])=>{
  const next=prefix?`${prefix}.${key}`:key;
  if(typeof item==="number"&&Number.isFinite(item))return [next];
  return item&&typeof item==="object"&&!Array.isArray(item)?numericPaths(item,next):[];
 });
};
'@.TrimEnd()

if ($Content.Contains($OldHelpers)) {
    $Content = $Content.Replace($OldHelpers, $NewHelpers)
}
elseif (-not $Content.Contains('const numericPaths=')) {
    throw "Digital Twin helper anchor was not found."
}

$Content = $Content.Replace(
    ' const [path,setPath]=useState("reservoir.pressure");',
    ' const [path,setPath]=useState("");'
)

$OldTwinBlock = @'
 const twin=summary.data?.twin;
 const reservoirEntries=useMemo(()=>entries(twin?.reservoir??twin?.metrics??{}),[twin]);
'@.TrimEnd()

$NewTwinBlock = @'
 const twin=summary.data?.twin;
 const availablePaths=useMemo(()=>numericPaths(twin),[twin]);
 const reservoirEntries=useMemo(()=>entries(twin?.reservoir??twin?.metrics??{}),[twin]);
 useEffect(()=>{if(path&&!availablePaths.includes(path))setPath("");if(!path&&availablePaths.length)setPath(availablePaths[0])},[availablePaths,path]);
'@.TrimEnd()

if ($Content.Contains($OldTwinBlock)) {
    $Content = $Content.Replace($OldTwinBlock, $NewTwinBlock)
}
elseif (-not $Content.Contains('const availablePaths=useMemo')) {
    throw "Twin state anchor was not found."
}

$OldPathControl = '<TextField label="State path" value={path} onChange={e=>setPath(e.target.value)} helperText="Example: reservoir.pressure or wells.GABO-18.water_rate"/>'
$NewPathControl = @'
{availablePaths.length?<FormControl><InputLabel>State path</InputLabel><Select label="State path" value={path} onChange={e=>setPath(e.target.value)}>{availablePaths.map(item=><MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl>:<Alert severity="info">No numeric twin-state fields are available yet. Ingest reservoir or well-state data through Streaming, Workflows or the twin update API before running a scenario.</Alert>}
'@.TrimEnd()

if ($Content.Contains($OldPathControl)) {
    $Content = $Content.Replace($OldPathControl, $NewPathControl)
}

$OldScenarioButton = 'disabled={!path.trim()||!Number.isFinite(Number(value))||scenario.isPending}'
$NewScenarioButton = 'disabled={!id||scenarioName.trim().length<2||!availablePaths.includes(path)||!Number.isFinite(Number(value))||scenario.isPending}'

if ($Content.Contains($OldScenarioButton)) {
    $Content = $Content.Replace($OldScenarioButton, $NewScenarioButton)
}

Write-Host "[4/5] Correcting dialog focus handling and post-create refresh..." -ForegroundColor Cyan

$CreateMutationOld = ' const create=useMutation({mutationFn:()=>createTwin({reservoir_id:reservoirId.trim(),name:name.trim()}),onSuccess:async x=>{setSelected(x.reservoir_id);setCreateOpen(false);await qc.invalidateQueries({queryKey:["twins"]})}});'
$CreateMutationNew = @'
 const closeCreate=()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();setCreateOpen(false)};
 const create=useMutation({mutationFn:()=>createTwin({reservoir_id:reservoirId.trim(),name:name.trim()}),onSuccess:async x=>{setSelected(x.reservoir_id);closeCreate();await qc.invalidateQueries({queryKey:["twins"]});await qc.refetchQueries({queryKey:["twins"]})}});
'@.TrimEnd()

if ($Content.Contains($CreateMutationOld)) {
    $Content = $Content.Replace($CreateMutationOld, $CreateMutationNew)
}
elseif (-not $Content.Contains('const closeCreate=')) {
    throw "Create mutation anchor was not found."
}

$Content = $Content.Replace(
    '<Dialog open={createOpen} onClose={()=>setCreateOpen(false)}',
    '<Dialog open={createOpen} onClose={closeCreate}'
)
$Content = $Content.Replace(
    '<Button onClick={()=>setCreateOpen(false)}>Cancel</Button>',
    '<Button onClick={closeCreate}>Cancel</Button>'
)

Write-Utf8NoBom -Path $Panel -Content $Content

Set-Location $Root

Write-Host "[5/5] Rebuilding and verifying frontend..." -ForegroundColor Cyan

docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed. Backup: $Backup"
}

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
if ($Index.StatusCode -ne 200) {
    throw "Frontend returned HTTP $($Index.StatusCode). Backup: $Backup"
}

$Markers = docker compose exec -T frontend sh -lc `
    "grep -R -l 'No numeric twin-state fields are available yet' /usr/share/nginx/html/assets 2>/dev/null || true" 2>&1

@(
    "PETROEDGE AI PHASE 5 TWIN RUNTIME STABILITY RESULT"
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
    "Backup: $Backup"
    "Frontend status: $($Index.StatusCode)"
    ""
    "Compiled marker search:"
    $Markers
    ""
    "$(docker compose ps -a | Out-String)"
) | Set-Content -LiteralPath $Result -Encoding utf8

Write-Host ""
Write-Host "DIGITAL TWIN RUNTIME STABILITY FIX COMPLETED" -ForegroundColor Green
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
Write-Host "Close all PetroEdge tabs, reopen http://localhost:5173, then press Ctrl+Shift+R." -ForegroundColor Yellow
