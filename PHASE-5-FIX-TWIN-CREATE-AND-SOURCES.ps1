$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $Root "patch-backups\phase5-twin-create-fix-$Stamp"
$Result = Join-Path $Root "PHASE-5-TWIN-CREATE-FIX-RESULT.txt"

$TwinsRoute = Join-Path $Root "backend\app\api\routes\twins.py"
$Panel = Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"

foreach ($Path in @($TwinsRoute, $Panel)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required file not found: $Path"
    }
}

New-Item -ItemType Directory -Path $Backup -Force | Out-Null
Copy-Item $TwinsRoute (Join-Path $Backup "twins.py") -Force
Copy-Item $Panel (Join-Path $Backup "ReservoirDigitalTwinPanel.tsx") -Force

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Write-Host "[1/5] Correcting Digital Twin role permissions..." -ForegroundColor Cyan

$RouteContent = [System.IO.File]::ReadAllText($TwinsRoute)

$OldRead = 'READ_ROLES = ("admin", "geoscientist", "engineer", "viewer")'
$NewRead = 'READ_ROLES = ("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")'
$OldWrite = 'WRITE_ROLES = ("admin", "geoscientist", "engineer")'
$NewWrite = 'WRITE_ROLES = ("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist")'

if ($RouteContent.Contains($OldRead)) {
    $RouteContent = $RouteContent.Replace($OldRead, $NewRead)
}
elseif (-not $RouteContent.Contains($NewRead)) {
    throw "Expected READ_ROLES definition was not found."
}

if ($RouteContent.Contains($OldWrite)) {
    $RouteContent = $RouteContent.Replace($OldWrite, $NewWrite)
}
elseif (-not $RouteContent.Contains($NewWrite)) {
    throw "Expected WRITE_ROLES definition was not found."
}

Write-Utf8NoBom -Path $TwinsRoute -Content $RouteContent

Write-Host "[2/5] Connecting twin creation to Assets and surfacing API errors..." -ForegroundColor Cyan

$PanelContent = [System.IO.File]::ReadAllText($Panel)

$ImportOld = 'import {createTwin,deleteTwin,fetchDatasets,fetchTwinHistory,fetchTwins,fetchTwinWorkspaceSummary,restoreTwinVersion,runTwinWorkspaceScenario} from "./platformApi";'
$ImportNew = 'import {createTwin,deleteTwin,fetchAssets,fetchDatasets,fetchTwinHistory,fetchTwins,fetchTwinWorkspaceSummary,restoreTwinVersion,runTwinWorkspaceScenario} from "./platformApi";'

if ($PanelContent.Contains($ImportOld)) {
    $PanelContent = $PanelContent.Replace($ImportOld, $ImportNew)
}
elseif (-not $PanelContent.Contains($ImportNew)) {
    throw "Digital Twin API import anchor was not found."
}

$DatasetQueryAnchor = ' const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});'
$DatasetQueryReplacement = @'
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const assets=useQuery({queryKey:["assets"],queryFn:fetchAssets});
'@.TrimEnd()

if ($PanelContent.Contains($DatasetQueryAnchor) -and -not $PanelContent.Contains('const assets=useQuery')) {
    $PanelContent = $PanelContent.Replace($DatasetQueryAnchor, $DatasetQueryReplacement)
}

$DatasetStateAnchor = ' const [datasetId,setDatasetId]=useState("");'
$DatasetStateReplacement = ' const [datasetId,setDatasetId]=useState(""); const [assetId,setAssetId]=useState("");'

if ($PanelContent.Contains($DatasetStateAnchor) -and -not $PanelContent.Contains('const [assetId,setAssetId]')) {
    $PanelContent = $PanelContent.Replace($DatasetStateAnchor, $DatasetStateReplacement)
}

$DatasetEffect = ' useEffect(()=>{const ds=datasets.data?.find(x=>x.dataset_id===datasetId);if(ds){setReservoirId((ds.reservoir_name||ds.well_name||ds.name).replace(/\s+/g,"-").toUpperCase());setName(ds.reservoir_name||`${ds.name} Digital Twin`)}},[datasetId,datasets.data]);'
$EffectsReplacement = @'
 useEffect(()=>{const ds=datasets.data?.find(x=>x.dataset_id===datasetId);if(ds){setAssetId("");setReservoirId((ds.reservoir_name||ds.well_name||ds.name).replace(/\s+/g,"-").toUpperCase());setName(ds.reservoir_name||`${ds.name} Digital Twin`)}},[datasetId,datasets.data]);
 useEffect(()=>{const asset=assets.data?.find(x=>x.asset_id===assetId);if(asset){setDatasetId(asset.dataset_id??"");setReservoirId((asset.field||asset.well||asset.asset_id).replace(/\s+/g,"-").toUpperCase());setName(`${asset.field} · ${asset.well} Digital Twin`)}},[assetId,assets.data]);
'@.TrimEnd()

if ($PanelContent.Contains($DatasetEffect) -and -not $PanelContent.Contains('const asset=assets.data')) {
    $PanelContent = $PanelContent.Replace($DatasetEffect, $EffectsReplacement)
}

$EmptyAlert = '  {!id&&<Alert severity="info">Create or select a reservoir twin to initialise the workspace.</Alert>}'
$ErrorAlerts = @'
  {twins.isError&&<Alert severity="error">{twins.error instanceof Error?twins.error.message:"Reservoir twins could not be loaded. Check your role permissions and backend status."}</Alert>}
  {datasets.isError&&<Alert severity="error">Datasets could not be loaded for twin initialisation.</Alert>}
  {assets.isError&&<Alert severity="error">Assets could not be loaded for twin initialisation.</Alert>}
  {!id&&!twins.isError&&<Alert severity="info">No reservoir twin exists yet. Use Create twin, select a Dataset or Asset as the source context, then create the registry entry.</Alert>}
'@.TrimEnd()

if ($PanelContent.Contains($EmptyAlert)) {
    $PanelContent = $PanelContent.Replace($EmptyAlert, $ErrorAlerts)
}

$DialogAnchor = '<DialogContent><Stack spacing={2} mt={1}><FormControl><InputLabel>Source dataset</InputLabel>'
$DialogReplacement = @'
<DialogContent><Stack spacing={2} mt={1}>
<FormControl><InputLabel>Source asset</InputLabel><Select label="Source asset" value={assetId} onChange={e=>setAssetId(e.target.value)}><MenuItem value="">No asset selected</MenuItem>{(assets.data??[]).map(a=><MenuItem key={a.asset_id} value={a.asset_id}>{a.field} · {a.well}</MenuItem>)}</Select></FormControl>
<FormControl><InputLabel>Source dataset</InputLabel>
'@.TrimEnd()

if ($PanelContent.Contains($DialogAnchor) -and -not $PanelContent.Contains('<InputLabel>Source asset</InputLabel>')) {
    $PanelContent = $PanelContent.Replace($DialogAnchor, $DialogReplacement)
}

$CreateErrorOld = '{create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Twin creation failed."}</Alert>}'
$CreateErrorNew = '{create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Twin creation failed. Confirm that your account has a Digital Twin write role and that the reservoir ID is unique."}</Alert>}'

if ($PanelContent.Contains($CreateErrorOld)) {
    $PanelContent = $PanelContent.Replace($CreateErrorOld, $CreateErrorNew)
}

Write-Utf8NoBom -Path $Panel -Content $PanelContent

Set-Location $Root

Write-Host "[3/5] Validating Docker Compose..." -ForegroundColor Cyan
docker compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose validation failed."
}

Write-Host "[4/5] Rebuilding backend and frontend..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate --remove-orphans
if ($LASTEXITCODE -ne 0) {
    throw "Docker rebuild failed. Backup: $Backup"
}

Write-Host "[5/5] Verifying health and twin access..." -ForegroundColor Cyan

$Healthy = $false
for ($Attempt = 1; $Attempt -le 35; $Attempt++) {
    try {
        $Health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
        if ($Health.status -in @("ok", "healthy", "degraded")) {
            $Healthy = $true
            break
        }
    }
    catch {}
    Start-Sleep -Seconds 4
}

if (-not $Healthy) {
    docker compose logs backend --tail 250
    throw "Backend did not become healthy. Backup: $Backup"
}

$OpenApi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json" -TimeoutSec 30
$Paths = @($OpenApi.paths.PSObject.Properties.Name)
$Required = @(
    "/api/v1/twins",
    "/api/v1/twins/{reservoir_id}",
    "/api/v1/twin-workspace/{reservoir_id}/summary"
)
$Missing = @($Required | Where-Object { $Paths -notcontains $_ })

@(
    "PETROEDGE AI PHASE 5 TWIN CREATE FIX RESULT"
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
    "Backup: $Backup"
    "Missing required paths: $($Missing.Count)"
    ""
    "Corrected roles:"
    $NewRead
    $NewWrite
    ""
    "$(docker compose ps -a | Out-String)"
) | Set-Content -LiteralPath $Result -Encoding utf8

if ($Missing.Count -gt 0) {
    throw "Twin API routes are missing. Review: $Result"
}

Write-Host ""
Write-Host "DIGITAL TWIN CREATE AND SOURCE-CONNECTION FIX COMPLETED" -ForegroundColor Green
Write-Host "Refresh with Ctrl+Shift+R and open Digital Twin." -ForegroundColor Yellow
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
