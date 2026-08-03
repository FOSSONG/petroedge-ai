$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$Root="C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$Backup=Join-Path $Root "patch-backups\phase5-digital-twin-$Stamp"
$Result=Join-Path $Root "PHASE-5-DIGITAL-TWIN-IMPLEMENTATION-RESULT.txt"

$Main=Join-Path $Root "backend\app\main.py"
$Facade=Join-Path $Root "backend\app\api\routes\twin_workspace.py"
$Api=Join-Path $Root "frontend\src\features\platform\platformApi.ts"
$Panel=Join-Path $Root "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
$Dashboard=Join-Path $Root "frontend\src\features\dashboard\DashboardPage.tsx"

function WriteUtf8([string]$Path,[string]$Text){
 New-Item -ItemType Directory -Force -Path (Split-Path $Path)|Out-Null
 [IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))
}
function BackupFile([string]$Path,[string]$Rel){
 if(Test-Path $Path){
  $Dest=Join-Path $Backup $Rel
  New-Item -ItemType Directory -Force -Path (Split-Path $Dest)|Out-Null
  Copy-Item $Path $Dest -Force
 }
}
foreach($p in @($Main,$Api,$Dashboard)){if(-not(Test-Path $p)){throw "Missing required file: $p"}}
New-Item -ItemType Directory -Force -Path $Backup|Out-Null
BackupFile $Main "backend\app\main.py"
BackupFile $Facade "backend\app\api\routes\twin_workspace.py"
BackupFile $Api "frontend\src\features\platform\platformApi.ts"
BackupFile $Panel "frontend\src\features\platform\ReservoirDigitalTwinPanel.tsx"
BackupFile $Dashboard "frontend\src\features\dashboard\DashboardPage.tsx"

$facadeText=@'
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.rbac import require_roles
from app.digital_twin import TwinRegistryError, health_engine, twin_history, twin_registry

router = APIRouter()
READ = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist", "viewer")
WRITE = require_roles("admin", "administrator", "operator", "engineer", "geoscientist", "petrophysicist")


class ScenarioAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=300)
    operation: Literal["set", "increase", "decrease", "multiply"]
    value: float


class WorkspaceScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=200)
    adjustments: list[ScenarioAdjustment] = Field(min_length=1, max_length=25)


def _get_parent(document: dict[str, Any], path: str) -> tuple[dict[str, Any], str]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise ValueError("Scenario path cannot be empty.")
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"Unknown scenario path: {path}")
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"Scenario path is not editable: {path}")
    return current, parts[-1]


def _apply(document: dict[str, Any], item: ScenarioAdjustment) -> dict[str, Any]:
    parent, key = _get_parent(document, item.path)
    if key not in parent:
        raise ValueError(f"Unknown scenario path: {item.path}")
    before = parent[key]
    if item.operation == "set":
        after: Any = item.value
    else:
        if not isinstance(before, (int, float)):
            raise ValueError(f"{item.operation.title()} requires a numeric value: {item.path}")
        if item.operation == "increase":
            after = float(before) + item.value
        elif item.operation == "decrease":
            after = float(before) - item.value
        else:
            after = float(before) * item.value
    parent[key] = after
    return {"path": item.path, "operation": item.operation, "before": before, "after": after}


@router.get("/{reservoir_id}/summary")
def summary(reservoir_id: str, _: dict[str, Any] = Depends(READ)) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
        health = health_engine.evaluate(twin)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    history = twin_history.list(reservoir_id)
    return {
        "twin": twin.model_dump(mode="json"),
        "health": health.model_dump(mode="json"),
        "history_count": len(history),
        "latest_version": history[-1].version if history else None,
        "methodology": {
            "classification": "operational digital-twin state management",
            "scenario_mode": "non-persistent transparent state perturbation",
            "limitations": [
                "Not a full-physics reservoir simulator",
                "No automatic history matching",
                "No calibrated production forecast unless supplied by a validated model",
            ],
        },
    }


@router.post("/{reservoir_id}/scenario")
def scenario(
    reservoir_id: str,
    request: WorkspaceScenarioRequest,
    _: dict[str, Any] = Depends(WRITE),
) -> dict[str, Any]:
    try:
        twin = twin_registry.get(reservoir_id)
    except TwinRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    baseline = twin.model_dump(mode="json")
    scenario_state = deepcopy(baseline)
    changes: list[dict[str, Any]] = []
    try:
        for adjustment in request.adjustments:
            changes.append(_apply(scenario_state, adjustment))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "reservoir_id": reservoir_id,
        "scenario_name": request.name,
        "persisted": False,
        "baseline": baseline,
        "scenario": scenario_state,
        "changes": changes,
        "warning": "Scenario comparison changes state values only. It is not a full-physics flow simulation.",
    }
'@
WriteUtf8 $Facade $facadeText

$mainText=[IO.File]::ReadAllText($Main)
if($mainText -notmatch '\("twin_workspace", "/twin-workspace"'){
 $anchor='    ("twins", "/twins", ("Reservoir Digital Twin",), True),'
 if(-not $mainText.Contains($anchor)){throw "Twin router anchor not found in main.py"}
 $mainText=$mainText.Replace($anchor,$anchor+[Environment]::NewLine+'    ("twin_workspace", "/twin-workspace", ("Digital Twin Workspace",), True),')
 WriteUtf8 $Main $mainText
}

$apiText=[IO.File]::ReadAllText($Api)
if($apiText -notmatch 'export interface ReservoirTwin'){
$apiText += @'

export interface ReservoirTwin {
  reservoir_id:string;
  name:string;
  version?:number;
  status?:string;
  wells?:Record<string,Record<string,unknown>>;
  reservoir?:Record<string,unknown>;
  metrics?:Record<string,unknown>;
  metadata?:Record<string,unknown>;
  updated_at?:string;
  created_at?:string;
  [key:string]:unknown;
}
export interface TwinListResponse {count:number;twins:ReservoirTwin[]}
export interface TwinHistoryResponse {reservoir_id:string;count:number;snapshots:Array<Record<string,unknown>>}
export interface TwinWorkspaceSummary {
 twin:ReservoirTwin;health:Record<string,unknown>;history_count:number;latest_version?:number|null;
 methodology:{classification:string;scenario_mode:string;limitations:string[]};
}
export interface TwinScenarioResponse {
 reservoir_id:string;scenario_name:string;persisted:boolean;baseline:Record<string,unknown>;
 scenario:Record<string,unknown>;changes:Array<{path:string;operation:string;before:unknown;after:unknown}>;warning:string;
}
export const fetchTwins=()=>apiRequest<TwinListResponse>("/twins");
export const createTwin=(payload:{reservoir_id:string;name:string})=>apiRequest<ReservoirTwin>("/twins",{method:"POST",body:JSON.stringify(payload)});
export const fetchTwin=(reservoirId:string)=>apiRequest<ReservoirTwin>(`/twins/${reservoirId}`);
export const fetchTwinHealth=(reservoirId:string)=>apiRequest<Record<string,unknown>>(`/twins/${reservoirId}/health`);
export const fetchTwinHistory=(reservoirId:string)=>apiRequest<TwinHistoryResponse>(`/twins/${reservoirId}/history`);
export const restoreTwinVersion=(reservoirId:string,version:number)=>apiRequest<ReservoirTwin>(`/twins/${reservoirId}/restore/${version}`,{method:"POST"});
export const deleteTwin=(reservoirId:string)=>apiRequest<void>(`/twins/${reservoirId}`,{method:"DELETE"});
export const fetchTwinWorkspaceSummary=(reservoirId:string)=>apiRequest<TwinWorkspaceSummary>(`/twin-workspace/${reservoirId}/summary`);
export const runTwinWorkspaceScenario=(reservoirId:string,payload:{name:string;adjustments:Array<{path:string;operation:"set"|"increase"|"decrease"|"multiply";value:number}>})=>
 apiRequest<TwinScenarioResponse>(`/twin-workspace/${reservoirId}/scenario`,{method:"POST",body:JSON.stringify(payload)});
'@
WriteUtf8 $Api $apiText
}

$panelText=@'
import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Box,Button,Chip,Dialog,DialogActions,DialogContent,DialogTitle,FormControl,Grid,InputLabel,LinearProgress,MenuItem,Paper,Select,Stack,Tab,Tabs,TextField,Typography} from "@mui/material";
import {Activity,Database,History,Orbit,Play,RefreshCw,RotateCcw,ShieldCheck,Trash2} from "lucide-react";
import {createTwin,deleteTwin,fetchDatasets,fetchTwinHistory,fetchTwins,fetchTwinWorkspaceSummary,restoreTwinVersion,runTwinWorkspaceScenario} from "./platformApi";

const entries=(value:unknown)=>value&&typeof value==="object"&&!Array.isArray(value)?Object.entries(value as Record<string,unknown>):[];
const label=(value:string)=>value.replace(/_/g," ");
const display=(value:unknown)=>typeof value==="number"?value.toLocaleString(undefined,{maximumFractionDigits:4}):typeof value==="boolean"?(value?"Yes":"No"):String(value??"—");

export function ReservoirDigitalTwinPanel(){
 const qc=useQueryClient();
 const twins=useQuery({queryKey:["twins"],queryFn:fetchTwins});
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [selected,setSelected]=useState("");
 const [tab,setTab]=useState(0);
 const [createOpen,setCreateOpen]=useState(false);
 const [datasetId,setDatasetId]=useState("");
 const [reservoirId,setReservoirId]=useState("");
 const [name,setName]=useState("");
 const [scenarioName,setScenarioName]=useState("Pressure sensitivity");
 const [path,setPath]=useState("reservoir.pressure");
 const [operation,setOperation]=useState<"set"|"increase"|"decrease"|"multiply">("increase");
 const [value,setValue]=useState("1");
 const id=selected||(twins.data?.twins[0]?.reservoir_id??"");
 const summary=useQuery({queryKey:["twin-workspace",id],queryFn:()=>fetchTwinWorkspaceSummary(id),enabled:Boolean(id)});
 const history=useQuery({queryKey:["twin-history",id],queryFn:()=>fetchTwinHistory(id),enabled:Boolean(id)});
 useEffect(()=>{const ds=datasets.data?.find(x=>x.dataset_id===datasetId);if(ds){setReservoirId((ds.reservoir_name||ds.well_name||ds.name).replace(/\s+/g,"-").toUpperCase());setName(ds.reservoir_name||`${ds.name} Digital Twin`)}},[datasetId,datasets.data]);
 const refresh=async()=>{await Promise.all([twins.refetch(),summary.refetch(),history.refetch()])};
 const create=useMutation({mutationFn:()=>createTwin({reservoir_id:reservoirId.trim(),name:name.trim()}),onSuccess:async x=>{setSelected(x.reservoir_id);setCreateOpen(false);await qc.invalidateQueries({queryKey:["twins"]})}});
 const remove=useMutation({mutationFn:deleteTwin,onSuccess:async()=>{setSelected("");await qc.invalidateQueries({queryKey:["twins"]})}});
 const restore=useMutation({mutationFn:(version:number)=>restoreTwinVersion(id,version),onSuccess:async()=>{await Promise.all([qc.invalidateQueries({queryKey:["twin-workspace",id]}),qc.invalidateQueries({queryKey:["twin-history",id]})])}});
 const scenario=useMutation({mutationFn:()=>runTwinWorkspaceScenario(id,{name:scenarioName,adjustments:[{path,operation,value:Number(value)}]})});
 const twin=summary.data?.twin;
 const reservoirEntries=useMemo(()=>entries(twin?.reservoir??twin?.metrics??{}),[twin]);
 if(twins.isLoading)return <LinearProgress/>;
 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4}}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Box><Stack direction="row" gap={1.5} alignItems="center"><Orbit/><Typography variant="h4" fontWeight={900}>Reservoir Digital Twin</Typography></Stack><Typography mt={1}>Create, inspect, version and test non-persistent reservoir-state scenarios using the existing PetroEdge twin engine.</Typography></Box><Stack direction="row" gap={1}><Button variant="contained" startIcon={<RefreshCw/>} onClick={refresh}>Refresh</Button><Button variant="contained" startIcon={<Database/>} onClick={()=>setCreateOpen(true)}>Create twin</Button></Stack></Stack></Paper>
  <Alert severity="info">The scenario tool performs transparent state perturbation for engineering sensitivity review. It does not claim full-physics flow simulation, automatic history matching or calibrated forecasting.</Alert>
  <Paper variant="outlined" sx={{p:2.5}}><Stack direction={{xs:"column",md:"row"}} gap={2} alignItems={{md:"center"}}><FormControl fullWidth><InputLabel>Reservoir twin</InputLabel><Select label="Reservoir twin" value={id} onChange={e=>{setSelected(e.target.value);scenario.reset()}}><MenuItem value="">No twin selected</MenuItem>{(twins.data?.twins??[]).map(x=><MenuItem value={x.reservoir_id} key={x.reservoir_id}>{x.name} · {x.reservoir_id}</MenuItem>)}</Select></FormControl>{id&&<><Chip icon={<History size={15}/>} label={`${summary.data?.history_count??0} versions`}/><Chip color="success" icon={<ShieldCheck size={15}/>} label={String((summary.data?.health as Record<string,unknown>|undefined)?.status??"evaluated")}/><Button color="error" startIcon={<Trash2/>} onClick={()=>remove.mutate(id)}>Delete</Button></>}</Stack></Paper>
  {!id&&<Alert severity="info">Create or select a reservoir twin to initialise the workspace.</Alert>}
  {id&&<><Paper variant="outlined"><Tabs value={tab} onChange={(_,v)=>setTab(v)} variant="scrollable"><Tab label="State overview"/><Tab label="Scenario comparison"/><Tab label="Version history"/></Tabs></Paper>
   {summary.isLoading&&<LinearProgress/>}
   {summary.isError&&<Alert severity="error">{summary.error instanceof Error?summary.error.message:"Twin summary could not be loaded."}</Alert>}
   {tab===0&&twin&&<Grid container spacing={2}>
    <Grid item xs={12} md={4}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="overline">Identity</Typography><Typography variant="h5">{twin.name}</Typography><Typography color="text.secondary">{twin.reservoir_id}</Typography><Stack direction="row" gap={1} mt={2} flexWrap="wrap"><Chip label={`Version ${String(twin.version??summary.data?.latest_version??"—")}`}/><Chip label={String(twin.status??"active")}/></Stack></Paper></Grid>
    <Grid item xs={12} md={8}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="h6">Reservoir state</Typography>{reservoirEntries.length===0?<Typography color="text.secondary" mt={1}>No reservoir-state fields have been ingested yet. Streaming and workflow updates will populate this state.</Typography>:<Grid container spacing={1.5} mt={.5}>{reservoirEntries.slice(0,16).map(([k,v])=><Grid item xs={6} md={3} key={k}><Paper variant="outlined" sx={{p:1.5}}><Typography variant="caption" color="text.secondary">{label(k)}</Typography><Typography fontWeight={800}>{display(v)}</Typography></Paper></Grid>)}</Grid>}</Paper></Grid>
    <Grid item xs={12}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Health evaluation</Typography><Stack direction="row" gap={1} flexWrap="wrap" mt={1}>{entries(summary.data?.health).map(([k,v])=><Chip key={k} label={`${label(k)}: ${display(v)}`}/>)}</Stack></Paper></Grid>
   </Grid>}
   {tab===1&&<Grid container spacing={2}><Grid item xs={12} md={5}><Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Typography variant="h6">Non-persistent scenario</Typography><TextField label="Scenario name" value={scenarioName} onChange={e=>setScenarioName(e.target.value)}/><TextField label="State path" value={path} onChange={e=>setPath(e.target.value)} helperText="Example: reservoir.pressure or wells.GABO-18.water_rate"/><FormControl><InputLabel>Operation</InputLabel><Select label="Operation" value={operation} onChange={e=>setOperation(e.target.value as typeof operation)}>{["set","increase","decrease","multiply"].map(x=><MenuItem value={x} key={x}>{x}</MenuItem>)}</Select></FormControl><TextField type="number" label="Value" value={value} onChange={e=>setValue(e.target.value)}/>{scenario.isError&&<Alert severity="error">{scenario.error instanceof Error?scenario.error.message:"Scenario failed."}</Alert>}<Button variant="contained" startIcon={<Play/>} disabled={!path.trim()||!Number.isFinite(Number(value))||scenario.isPending} onClick={()=>scenario.mutate()}>{scenario.isPending?"Running…":"Compare scenario"}</Button></Stack></Paper></Grid>
   <Grid item xs={12} md={7}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="h6">Scenario delta</Typography>{!scenario.data?<Typography color="text.secondary" mt={1}>Run a scenario to compare baseline and adjusted state values.</Typography>:<Stack spacing={1.5} mt={2}>{scenario.data.changes.map(x=><Paper key={x.path} variant="outlined" sx={{p:2}}><Typography fontWeight={800}>{x.path}</Typography><Stack direction="row" gap={1} mt={1}><Chip label={`Baseline: ${display(x.before)}`}/><Chip color="primary" label={`Scenario: ${display(x.after)}`}/><Chip label={x.operation}/></Stack></Paper>)}<Alert severity="warning">{scenario.data.warning}</Alert></Stack>}</Paper></Grid></Grid>}
   {tab===2&&<Paper variant="outlined" sx={{p:3}}><Typography variant="h6" mb={2}>Version history</Typography>{history.isLoading&&<LinearProgress/>}<Stack spacing={1.5}>{(history.data?.snapshots??[]).slice().reverse().map((x,i)=>{const version=Number((x as Record<string,unknown>).version??history.data!.count-i);return <Paper variant="outlined" sx={{p:2}} key={`${version}-${i}`}><Stack direction={{xs:"column",sm:"row"}} justifyContent="space-between"><Box><Typography fontWeight={800}>Version {version}</Typography><Typography variant="body2" color="text.secondary">{display((x as Record<string,unknown>).created_at??(x as Record<string,unknown>).timestamp)}</Typography></Box><Button startIcon={<RotateCcw/>} disabled={restore.isPending} onClick={()=>restore.mutate(version)}>Restore</Button></Stack></Paper>})}</Stack></Paper>}
  </>}
  <Dialog open={createOpen} onClose={()=>setCreateOpen(false)} fullWidth maxWidth="sm"><DialogTitle>Create reservoir twin</DialogTitle><DialogContent><Stack spacing={2} mt={1}><FormControl><InputLabel>Source dataset</InputLabel><Select label="Source dataset" value={datasetId} onChange={e=>setDatasetId(e.target.value)}><MenuItem value="">Manual identity</MenuItem>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl><TextField label="Reservoir ID" required value={reservoirId} onChange={e=>setReservoirId(e.target.value)}/><TextField label="Twin name" required value={name} onChange={e=>setName(e.target.value)}/>{create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Twin creation failed."}</Alert>}</Stack></DialogContent><DialogActions><Button onClick={()=>setCreateOpen(false)}>Cancel</Button><Button variant="contained" disabled={reservoirId.trim().length<2||name.trim().length<2||create.isPending} onClick={()=>create.mutate()}>Create</Button></DialogActions></Dialog>
 </Stack>
}
'@
WriteUtf8 $Panel $panelText

$dash=[IO.File]::ReadAllText($Dashboard)
$importAnchor='const DigitalReplayPanel = lazy(() => import("../platform/DigitalReplayPanel").then((m) => ({ default: m.DigitalReplayPanel })));'
$newImport='const ReservoirDigitalTwinPanel = lazy(() => import("../platform/ReservoirDigitalTwinPanel").then((m) => ({ default: m.ReservoirDigitalTwinPanel })));'
if(-not $dash.Contains($newImport)){
 if(-not $dash.Contains($importAnchor)){throw "DigitalReplay import anchor not found"}
 $dash=$dash.Replace($importAnchor,$importAnchor+[Environment]::NewLine+$newImport)
}
$tabAnchor='    { label: "Digital Replay", icon: <PlayCircle size={17} />, panel: <DigitalReplayPanel /> },'
$newTab='    { label: "Digital Twin", icon: <Orbit size={17} />, panel: <ReservoirDigitalTwinPanel /> },'
if(-not $dash.Contains($newTab)){
 if(-not $dash.Contains($tabAnchor)){throw "Digital Replay tab anchor not found"}
 $dash=$dash.Replace($tabAnchor,$newTab+[Environment]::NewLine+$tabAnchor)
}
if($dash -notmatch '\bOrbit,'){
 $iconAnchor='  Moon,'
 if(-not $dash.Contains($iconAnchor)){throw "Icon import anchor not found"}
 $dash=$dash.Replace($iconAnchor,'  Orbit,'+[Environment]::NewLine+$iconAnchor)
}
$dash=$dash.Replace('"digital-twin": "Interactive Logs"','"digital-twin": "Digital Twin"')
WriteUtf8 $Dashboard $dash

Set-Location $Root
Write-Host "[1/4] Validating Compose..." -ForegroundColor Cyan
docker compose config --quiet
if($LASTEXITCODE-ne0){throw "Compose validation failed."}

Write-Host "[2/4] Rebuilding application..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate --remove-orphans
if($LASTEXITCODE-ne0){throw "Docker rebuild failed. Backup: $Backup"}

Write-Host "[3/4] Waiting for backend..." -ForegroundColor Cyan
$ok=$false
for($i=0;$i-lt35;$i++){
 try{$h=Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 10;if($h.status-in@("ok","healthy","degraded")){$ok=$true;break}}catch{}
 Start-Sleep 4
}
if(-not$ok){docker compose logs backend --tail 250;throw "Backend did not become healthy. Backup: $Backup"}

Write-Host "[4/4] Verifying twin routes..." -ForegroundColor Cyan
$o=Invoke-RestMethod "http://localhost:8000/openapi.json" -TimeoutSec 30
$paths=@($o.paths.PSObject.Properties.Name)
$required=@(
 "/api/v1/twins",
 "/api/v1/twins/{reservoir_id}",
 "/api/v1/twins/{reservoir_id}/health",
 "/api/v1/twins/{reservoir_id}/history",
 "/api/v1/twins/{reservoir_id}/restore/{version}",
 "/api/v1/twins/{reservoir_id}/simulate",
 "/api/v1/twin-workspace/{reservoir_id}/summary",
 "/api/v1/twin-workspace/{reservoir_id}/scenario"
)
$missing=@($required|Where-Object{$paths-notcontains$_})
@(
"PETROEDGE AI PHASE 5 DIGITAL TWIN IMPLEMENTATION RESULT"
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
"Backup: $Backup"
"Missing required paths: $($missing.Count)"
$($missing|ForEach-Object{"MISSING: $_"})
""
"$(docker compose ps -a|Out-String)"
)|Set-Content $Result -Encoding utf8
if($missing.Count-gt0){throw "Digital Twin routes missing. Review $Result"}
Write-Host ""
Write-Host "PHASE 5 DIGITAL TWIN IMPLEMENTATION COMPLETED" -ForegroundColor Green
Write-Host "Refresh with Ctrl+F5 and open Digital Twin." -ForegroundColor Yellow
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
