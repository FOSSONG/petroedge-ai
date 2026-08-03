$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$Root="C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$Backup=Join-Path $Root "patch-backups\phase4-ccus-$Stamp"
$Result=Join-Path $Root "PHASE-4-CCUS-IMPLEMENTATION-RESULT.txt"
$Main=Join-Path $Root "backend\app\main.py"
$Route=Join-Path $Root "backend\app\api\routes\ccus.py"
$Api=Join-Path $Root "frontend\src\features\platform\platformApi.ts"
$Panel=Join-Path $Root "frontend\src\features\platform\CcusWorkspacePanel.tsx"

function WriteUtf8([string]$Path,[string]$Text){
  New-Item -ItemType Directory -Force -Path (Split-Path $Path) | Out-Null
  [IO.File]::WriteAllText($Path,$Text,(New-Object Text.UTF8Encoding($false)))
}
function Backup([string]$Path,[string]$Rel){
  if(Test-Path $Path){
    $Dest=Join-Path $Backup $Rel
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    Copy-Item $Path $Dest -Force
  }
}
foreach($p in @($Main,$Api,$Panel)){if(-not(Test-Path $p)){throw "Missing required file: $p"}}
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
Backup $Main "backend\app\main.py"
Backup $Route "backend\app\api\routes\ccus.py"
Backup $Api "frontend\src\features\platform\platformApi.ts"
Backup $Panel "frontend\src\features\platform\CcusWorkspacePanel.tsx"

$routeText=@'
from __future__ import annotations
import json, math, os, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.rbac import require_roles
from app.platform_v1.datasets import get_dataset

router=APIRouter()
READ=require_roles("admin","administrator","operator","engineer","geoscientist","petrophysicist","viewer")
WRITE=require_roles("admin","administrator","operator","engineer","geoscientist","petrophysicist")
ROOT=Path(__file__).resolve().parents[3]
DB=Path(os.getenv("PETROEDGE_DATA_DIR",str(ROOT/"data"))).resolve()/"ccus_runs.db"

def now(): return datetime.now(timezone.utc).isoformat()
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(str(DB),timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); return c
def initialise():
    with closing(connect()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ccus_runs(
        run_id TEXT PRIMARY KEY,project_name TEXT NOT NULL,dataset_id TEXT,dataset_name TEXT,
        field_name TEXT,well_name TEXT,reservoir_name TEXT,storage_type TEXT NOT NULL,
        capacity_mt REAL NOT NULL,pore_volume_m3 REAL NOT NULL,suitability_score REAL NOT NULL,
        suitability_class TEXT NOT NULL,injectivity_score REAL NOT NULL,containment_score REAL NOT NULL,
        data_quality_score REAL NOT NULL,pressure_margin_mpa REAL NOT NULL,risk_flags_json TEXT NOT NULL,
        recommendations_json TEXT NOT NULL,inputs_json TEXT NOT NULL,methodology_json TEXT NOT NULL,
        created_at TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_ccus_runs_created ON ccus_runs(created_at DESC)")
        c.commit()
initialise()

class Screen(BaseModel):
    model_config=ConfigDict(extra="forbid")
    dataset_id:str|None=Field(default=None,max_length=200)
    project_name:str=Field(min_length=2,max_length=200)
    storage_type:Literal["saline_aquifer","depleted_reservoir"]="saline_aquifer"
    area_km2:float=Field(gt=0,le=100000)
    net_thickness_m:float=Field(gt=0,le=5000)
    porosity_fraction:float=Field(gt=0,le=.60)
    co2_density_kg_m3:float=Field(ge=100,le=1200)
    storage_efficiency_fraction:float=Field(gt=0,le=.40)
    permeability_md:float=Field(ge=0,le=1000000)
    depth_m:float=Field(gt=0,le=15000)
    initial_pressure_mpa:float=Field(ge=0,le=200)
    fracture_pressure_mpa:float=Field(gt=0,le=300)
    caprock_thickness_m:float|None=Field(default=None,ge=0,le=5000)
    fault_risk:Literal["low","medium","high","unknown"]="unknown"
    pressure_data_available:bool=False
    seal_data_available:bool=False
    fault_data_available:bool=False
    geomechanics_available:bool=False
    notes:str|None=Field(default=None,max_length=2000)
    @field_validator("project_name")
    @classmethod
    def clean(cls,v):
        v=v.strip()
        if not v: raise ValueError("Project name cannot be blank.")
        return v

def clamp(v,a=0,b=100): return max(a,min(b,float(v)))
def classify(v): return "high-potential" if v>=75 else "conditional" if v>=55 else "low-confidence" if v>=35 else "unsuitable"
def calculate(p:Screen):
    area=p.area_km2*1_000_000
    pore=area*p.net_thickness_m*p.porosity_fraction
    capacity=pore*p.storage_efficiency_fraction*p.co2_density_kg_m3/1_000_000_000
    perm=clamp((math.log10(max(p.permeability_md,.01))+2)/6,0,1)
    inj=round(100*(.72*perm+.28*clamp(p.net_thickness_m/100,0,1)),2)
    cont=35+(min(p.caprock_thickness_m/2,25) if p.caprock_thickness_m is not None else 0)
    cont+=15 if p.seal_data_available else 0
    cont+=10 if p.fault_data_available else 0
    cont+=10 if p.geomechanics_available else 0
    cont+=dict(low=5,medium=-8,high=-25,unknown=-12)[p.fault_risk]
    cont=round(clamp(cont),2)
    dq=round(20*sum([p.pressure_data_available,p.seal_data_available,p.fault_data_available,p.geomechanics_available,bool(p.dataset_id)]),2)
    margin=p.fracture_pressure_mpa-p.initial_pressure_mpa
    score=round(.22*clamp(p.porosity_fraction/.25*100)+.20*inj+.25*cont+.13*dq+.10*clamp((p.depth_m-600)/14)+.10*clamp(margin/10*100),2)
    flags=[]
    if margin<=0: flags.append("Initial pressure is at or above the entered fracture-pressure limit.")
    elif margin<3: flags.append("Pressure margin is narrow and requires geomechanical verification.")
    if p.permeability_md<10: flags.append("Low permeability may materially constrain injectivity.")
    elif p.permeability_md<50: flags.append("Moderate-to-low permeability requires dynamic injection testing.")
    if p.caprock_thickness_m is None: flags.append("Caprock thickness has not been provided.")
    elif p.caprock_thickness_m<20: flags.append("Entered caprock thickness is below the screening preference of 20 m.")
    if p.fault_risk=="high": flags.append("High fault risk requires structural and geomechanical review.")
    elif p.fault_risk=="unknown": flags.append("Fault risk is unknown.")
    if not p.pressure_data_available: flags.append("Measured pressure data are unavailable.")
    if not p.seal_data_available: flags.append("Seal-characterisation evidence is unavailable.")
    if not p.fault_data_available: flags.append("Fault-framework evidence is unavailable.")
    if not p.geomechanics_available: flags.append("Geomechanical evidence is unavailable.")
    rec=["Advance to site-specific modelling and dynamic simulation." if score>=75 else "Retain as a candidate and close evidence gaps before ranking." if score>=55 else "Do not progress beyond screening until major uncertainties are reduced."]
    if not p.pressure_data_available: rec.append("Acquire formation-pressure and pressure-gradient data.")
    if not p.seal_data_available: rec.append("Characterise caprock continuity and entry pressure.")
    if not p.fault_data_available: rec.append("Map faults and evaluate reactivation and leakage pathways.")
    if not p.geomechanics_available or margin<3: rec.append("Perform geomechanical fracture-pressure and fault-reactivation analysis.")
    if p.permeability_md<50: rec.append("Run pressure-transient or injection testing.")
    rec.append("Treat capacity as a volumetric screening estimate, not a bankable reserve.")
    return dict(capacity_mt=round(capacity,4),pore_volume_m3=round(pore,2),suitability_score=score,
      suitability_class=classify(score),injectivity_score=inj,containment_score=cont,
      data_quality_score=dq,pressure_margin_mpa=round(margin,3),risk_flags=flags,recommendations=rec,
      methodology={"capacity_equation":"M_CO2 = A × h_net × phi × E_storage × rho_CO2",
      "limitations":["No plume simulation","No geomechanical forecast","No regulatory resource classification"]})

def serial(row):
    d=dict(row)
    for k in ("risk_flags_json","recommendations_json","inputs_json","methodology_json"):
        d[k.replace("_json","")]=json.loads(d.pop(k))
    return d

@router.get("/capabilities")
def capabilities(_:dict[str,Any]=Depends(READ)):
    return {"status":"operational","version":"1.0-screening","capabilities":["volumetric_storage_capacity","reservoir_suitability_scoring","injectivity_proxy","containment_scoring","persistent_runs"],"limitations":["No plume simulation","No geomechanical forecast"]}

@router.post("/screen",status_code=201)
def screen(p:Screen,_:dict[str,Any]=Depends(WRITE)):
    meta={"dataset_name":None,"field_name":None,"well_name":None,"reservoir_name":None}
    if p.dataset_id:
        try:
            ds=get_dataset(p.dataset_id)
        except KeyError as e:
            raise HTTPException(404,"Selected dataset was not found.") from e
        meta={"dataset_name":ds.name,"field_name":ds.field_name,"well_name":ds.well_name,"reservoir_name":ds.reservoir_name}
    r=calculate(p); rid=f"ccus-{uuid4().hex[:14]}"; created=now()
    vals=(rid,p.project_name,p.dataset_id,meta["dataset_name"],meta["field_name"],meta["well_name"],meta["reservoir_name"],p.storage_type,
    r["capacity_mt"],r["pore_volume_m3"],r["suitability_score"],r["suitability_class"],r["injectivity_score"],r["containment_score"],
    r["data_quality_score"],r["pressure_margin_mpa"],json.dumps(r["risk_flags"]),json.dumps(r["recommendations"]),json.dumps(p.model_dump()),json.dumps(r["methodology"]),created)
    with closing(connect()) as c:
        c.execute("INSERT INTO ccus_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",vals); c.commit()
        row=c.execute("SELECT * FROM ccus_runs WHERE run_id=?",(rid,)).fetchone()
    return serial(row)

@router.get("/runs")
def runs(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),_:dict[str,Any]=Depends(READ)):
    with closing(connect()) as c: rows=c.execute("SELECT * FROM ccus_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",(limit,offset)).fetchall()
    return [serial(x) for x in rows]

@router.get("/runs/{run_id}")
def run(run_id:str,_:dict[str,Any]=Depends(READ)):
    with closing(connect()) as c: row=c.execute("SELECT * FROM ccus_runs WHERE run_id=?",(run_id,)).fetchone()
    if row is None: raise HTTPException(404,"CCUS screening run not found.")
    return serial(row)

@router.delete("/runs/{run_id}",status_code=204)
def remove(run_id:str,_:dict[str,Any]=Depends(WRITE)):
    with closing(connect()) as c: cur=c.execute("DELETE FROM ccus_runs WHERE run_id=?",(run_id,)); c.commit()
    if cur.rowcount==0: raise HTTPException(404,"CCUS screening run not found.")
'@
WriteUtf8 $Route $routeText

$mainText=[IO.File]::ReadAllText($Main)
if($mainText -notmatch '\("ccus", "/ccus"'){
  $anchor='    ("assets", "/assets", ("Asset Management",), True),'
  if(-not $mainText.Contains($anchor)){throw "Assets router anchor not found."}
  $mainText=$mainText.Replace($anchor,$anchor+[Environment]::NewLine+'    ("ccus", "/ccus", ("CCUS Screening",), True),')
  WriteUtf8 $Main $mainText
}

$apiText=[IO.File]::ReadAllText($Api)
if($apiText -notmatch 'export interface CcusScreenPayload'){
$apiText += @'

export interface CcusScreenPayload {
  dataset_id?: string | null; project_name:string; storage_type:"saline_aquifer"|"depleted_reservoir";
  area_km2:number; net_thickness_m:number; porosity_fraction:number; co2_density_kg_m3:number;
  storage_efficiency_fraction:number; permeability_md:number; depth_m:number;
  initial_pressure_mpa:number; fracture_pressure_mpa:number; caprock_thickness_m?:number|null;
  fault_risk:"low"|"medium"|"high"|"unknown"; pressure_data_available:boolean;
  seal_data_available:boolean; fault_data_available:boolean; geomechanics_available:boolean;
}
export interface CcusRunSummary {
  run_id:string; project_name:string; dataset_id?:string|null; dataset_name?:string|null;
  field_name?:string|null; well_name?:string|null; reservoir_name?:string|null; storage_type:string;
  capacity_mt:number; pore_volume_m3:number; suitability_score:number; suitability_class:string;
  injectivity_score:number; containment_score:number; data_quality_score:number; pressure_margin_mpa:number;
  risk_flags:string[]; recommendations:string[]; inputs:Record<string,unknown>;
  methodology:Record<string,unknown>; created_at:string;
}
export const fetchCcusCapabilities=()=>apiRequest<{status:string;version:string;capabilities:string[];limitations:string[]}>("/ccus/capabilities");
export const fetchCcusRuns=()=>apiRequest<CcusRunSummary[]>("/ccus/runs");
export const createCcusScreen=(payload:CcusScreenPayload)=>apiRequest<CcusRunSummary>("/ccus/screen",{method:"POST",body:JSON.stringify(payload)});
export const deleteCcusRun=(runId:string)=>apiRequest<void>(`/ccus/runs/${runId}`,{method:"DELETE"});
'@
WriteUtf8 $Api $apiText
}

$panelText=@'
import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Box,Button,Checkbox,Chip,CircularProgress,FormControl,FormControlLabel,Grid,InputLabel,LinearProgress,MenuItem,Paper,Select,Stack,TextField,Typography} from "@mui/material";
import {Database,RefreshCw,Trash2} from "lucide-react";
import {createCcusScreen,deleteCcusRun,fetchCcusCapabilities,fetchCcusRuns,fetchDatasets,type CcusScreenPayload} from "./platformApi";
const n=(v:string,f=0)=>Number.isFinite(Number(v))?Number(v):f;
const colour=(s:number):"success"|"warning"|"error"=>s>=75?"success":s>=55?"warning":"error";

export function CcusWorkspacePanel(){
 const qc=useQueryClient();
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const caps=useQuery({queryKey:["ccus","capabilities"],queryFn:fetchCcusCapabilities});
 const runs=useQuery({queryKey:["ccus","runs"],queryFn:fetchCcusRuns});
 const [dataset,setDataset]=useState(""); const [name,setName]=useState("Niger Delta CCUS screening");
 const [type,setType]=useState<"saline_aquifer"|"depleted_reservoir">("saline_aquifer");
 const [area,setArea]=useState("10"),[h,setH]=useState("35"),[phi,setPhi]=useState("0.20"),[rho,setRho]=useState("650");
 const [eff,setEff]=useState("0.02"),[perm,setPerm]=useState("100"),[depth,setDepth]=useState("1800");
 const [pi,setPi]=useState("18"),[pf,setPf]=useState("28"),[seal,setSeal]=useState("40");
 const [fault,setFault]=useState<"low"|"medium"|"high"|"unknown">("unknown");
 const [pressureData,setPressureData]=useState(false),[sealData,setSealData]=useState(false),[faultData,setFaultData]=useState(false),[geo,setGeo]=useState(false);
 useEffect(()=>{if(!dataset&&datasets.data?.[0]?.dataset_id)setDataset(datasets.data[0].dataset_id)},[dataset,datasets.data]);
 const payload=useMemo<CcusScreenPayload>(()=>({dataset_id:dataset||null,project_name:name.trim(),storage_type:type,area_km2:n(area),net_thickness_m:n(h),porosity_fraction:n(phi),co2_density_kg_m3:n(rho),storage_efficiency_fraction:n(eff),permeability_md:n(perm),depth_m:n(depth),initial_pressure_mpa:n(pi),fracture_pressure_mpa:n(pf),caprock_thickness_m:seal.trim()?n(seal):null,fault_risk:fault,pressure_data_available:pressureData,seal_data_available:sealData,fault_data_available:faultData,geomechanics_available:geo}),[dataset,name,type,area,h,phi,rho,eff,perm,depth,pi,pf,seal,fault,pressureData,sealData,faultData,geo]);
 const create=useMutation({mutationFn:()=>createCcusScreen(payload),onSuccess:()=>qc.invalidateQueries({queryKey:["ccus","runs"]})});
 const remove=useMutation({mutationFn:deleteCcusRun,onSuccess:()=>qc.invalidateQueries({queryKey:["ccus","runs"]})});
 const latest=create.data??runs.data?.[0]; const valid=name.trim().length>1&&payload.area_km2>0&&payload.net_thickness_m>0&&payload.porosity_fraction>0&&payload.storage_efficiency_fraction>0&&payload.depth_m>0;
 if(datasets.isLoading||caps.isLoading)return <LinearProgress/>;
 return <Stack spacing={3}>
  <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}>
   <Box><Typography variant="h4" fontWeight={850}>CCUS Screening</Typography><Typography color="text.secondary">Transparent volumetric storage-capacity screening with injectivity, containment and evidence-quality diagnostics.</Typography></Box>
   <Stack direction="row" gap={1}><Chip icon={<Database size={16}/>} label={`${datasets.data?.length??0} datasets`}/><Chip color="success" label={caps.data?.status??"operational"}/><Button variant="outlined" startIcon={<RefreshCw size={16}/>} onClick={()=>void runs.refetch()}>Refresh</Button></Stack>
  </Stack>
  <Alert severity="info">Capacity uses MCO₂ = area × net thickness × porosity × storage efficiency × in-situ CO₂ density. Results are screening estimates, not dynamic simulation or regulatory storage classification.</Alert>
  <Grid container spacing={2}>
   <Grid item xs={12} lg={7}><Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
    <Typography variant="h6">Screening inputs</Typography>
    <Stack direction={{xs:"column",md:"row"}} gap={2}><TextField fullWidth label="Project name" value={name} onChange={e=>setName(e.target.value)}/><FormControl fullWidth><InputLabel>Dataset</InputLabel><Select label="Dataset" value={dataset} onChange={e=>setDataset(e.target.value)}><MenuItem value="">No dataset link</MenuItem>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl></Stack>
    <FormControl><InputLabel>Storage setting</InputLabel><Select label="Storage setting" value={type} onChange={e=>setType(e.target.value as typeof type)}><MenuItem value="saline_aquifer">Saline aquifer</MenuItem><MenuItem value="depleted_reservoir">Depleted reservoir</MenuItem></Select></FormControl>
    <Grid container spacing={2}>{[
      ["Area (km²)",area,setArea],["Net thickness (m)",h,setH],["Porosity (fraction)",phi,setPhi],["CO₂ density (kg/m³)",rho,setRho],
      ["Storage efficiency",eff,setEff],["Permeability (mD)",perm,setPerm],["Depth (m)",depth,setDepth],["Initial pressure (MPa)",pi,setPi],
      ["Fracture pressure (MPa)",pf,setPf],["Caprock thickness (m)",seal,setSeal]
    ].map(([label,value,setter])=><Grid item xs={12} sm={6} md={4} key={label as string}><TextField fullWidth type="number" label={label as string} value={value as string} onChange={e=>(setter as (v:string)=>void)(e.target.value)}/></Grid>)}
    <Grid item xs={12} sm={6} md={4}><FormControl fullWidth><InputLabel>Fault risk</InputLabel><Select label="Fault risk" value={fault} onChange={e=>setFault(e.target.value as typeof fault)}>{["unknown","low","medium","high"].map(x=><MenuItem key={x} value={x}>{x}</MenuItem>)}</Select></FormControl></Grid></Grid>
    <Box><Typography variant="subtitle2">Available evidence</Typography><Stack direction={{xs:"column",sm:"row"}} flexWrap="wrap">
     <FormControlLabel control={<Checkbox checked={pressureData} onChange={e=>setPressureData(e.target.checked)}/>} label="Pressure"/>
     <FormControlLabel control={<Checkbox checked={sealData} onChange={e=>setSealData(e.target.checked)}/>} label="Seal"/>
     <FormControlLabel control={<Checkbox checked={faultData} onChange={e=>setFaultData(e.target.checked)}/>} label="Fault"/>
     <FormControlLabel control={<Checkbox checked={geo} onChange={e=>setGeo(e.target.checked)}/>} label="Geomechanics"/>
    </Stack></Box>
    {create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Screening failed."}</Alert>}
    <Button variant="contained" size="large" disabled={!valid||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Calculating…":"Run CCUS screening"}</Button>
   </Stack></Paper></Grid>
   <Grid item xs={12} lg={5}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6" mb={2}>Latest result</Typography>
    {!latest&&<Typography color="text.secondary">Run a screening calculation to generate results.</Typography>}
    {latest&&<Stack spacing={2}><Stack direction="row" justifyContent="space-between"><Box><Typography variant="overline">Estimated capacity</Typography><Typography variant="h3" fontWeight={900}>{latest.capacity_mt.toLocaleString()} Mt</Typography></Box><Chip color={colour(latest.suitability_score)} label={latest.suitability_class}/></Stack>
    <Grid container spacing={1.5}>{[["Suitability",latest.suitability_score],["Injectivity",latest.injectivity_score],["Containment",latest.containment_score],["Data quality",latest.data_quality_score]].map(([l,s])=><Grid item xs={6} key={l as string}><Paper variant="outlined" sx={{p:1.5}}><Typography variant="caption">{l as string}</Typography><Typography variant="h6">{Number(s).toFixed(1)}%</Typography></Paper></Grid>)}</Grid>
    <Typography>Pressure margin: <strong>{latest.pressure_margin_mpa.toFixed(2)} MPa</strong></Typography>
    {latest.risk_flags.length>0&&<Alert severity="warning">{latest.risk_flags.map(x=><Typography key={x} variant="body2">• {x}</Typography>)}</Alert>}
    <Box><Typography variant="subtitle2">Recommended actions</Typography>{latest.recommendations.map(x=><Typography key={x} variant="body2" mt={.7}>• {x}</Typography>)}</Box>
    </Stack>}</Paper></Grid>
  </Grid>
  <Paper variant="outlined" sx={{p:3}}><Stack direction="row" justifyContent="space-between" mb={2}><Typography variant="h6">Auditable screening history</Typography><Chip label={`${runs.data?.length??0} runs`}/></Stack>
   {runs.isLoading&&<CircularProgress size={24}/>}<Stack spacing={1.5}>{(runs.data??[]).map(r=><Paper key={r.run_id} variant="outlined" sx={{p:2}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between"><Box><Typography fontWeight={800}>{r.project_name}</Typography><Typography variant="body2" color="text.secondary">{r.dataset_name??"No linked dataset"} · {r.storage_type.replaceAll("_"," ")} · {new Date(r.created_at).toLocaleString()}</Typography></Box><Stack direction="row" gap={1}><Chip label={`${r.capacity_mt.toLocaleString()} Mt`}/><Chip color={colour(r.suitability_score)} label={`${r.suitability_score.toFixed(1)}%`}/><Button size="small" color="error" startIcon={<Trash2 size={15}/>} onClick={()=>remove.mutate(r.run_id)}>Delete</Button></Stack></Stack></Paper>)}</Stack>
  </Paper>
 </Stack>
}
'@
WriteUtf8 $Panel $panelText

Set-Location $Root
Write-Host "[1/4] Validating Compose..." -ForegroundColor Cyan
docker compose config --quiet
if($LASTEXITCODE-ne0){throw "Compose validation failed."}

Write-Host "[2/4] Rebuilding..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate --remove-orphans
if($LASTEXITCODE-ne0){throw "Docker rebuild failed. Backup: $Backup"}

Write-Host "[3/4] Waiting for backend..." -ForegroundColor Cyan
$ok=$false
for($i=0;$i-lt35;$i++){
 try{$h=Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 10;if($h.status-in@("ok","healthy","degraded")){$ok=$true;break}}catch{}
 Start-Sleep 4
}
if(-not$ok){docker compose logs backend --tail 250;throw "Backend did not become healthy. Backup: $Backup"}

Write-Host "[4/4] Verifying CCUS routes..." -ForegroundColor Cyan
$o=Invoke-RestMethod "http://localhost:8000/openapi.json" -TimeoutSec 30
$paths=@($o.paths.PSObject.Properties.Name)
$required=@("/api/v1/ccus/capabilities","/api/v1/ccus/screen","/api/v1/ccus/runs","/api/v1/ccus/runs/{run_id}")
$missing=@($required|Where-Object{$paths-notcontains$_})
@(
"PETROEDGE AI PHASE 4 CCUS IMPLEMENTATION RESULT"
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
"Backup: $Backup"
"Missing CCUS paths: $($missing.Count)"
"Persistent database: backend\data\ccus_runs.db"
""
"$(docker compose ps -a | Out-String)"
)|Set-Content $Result -Encoding utf8
if($missing.Count-gt0){throw "CCUS routes missing. Review $Result"}
Write-Host ""
Write-Host "PHASE 4 CCUS IMPLEMENTATION COMPLETED" -ForegroundColor Green
Write-Host "Refresh with Ctrl+F5 and open CCUS." -ForegroundColor Yellow
Write-Host "Result: $Result"
Write-Host "Backup: $Backup"
