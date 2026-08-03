$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$Root="C:\Users\GUILIANNO FOSSONG\Documents\PetroEdge-AI-Release-4.0-COMBINED-WORKING"
$Stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$Backup=Join-Path $Root "patch-backups\phase6-digital-well-twin-$Stamp"
$Result=Join-Path $Root "PHASE-6-DIGITAL-WELL-TWIN-RESULT.txt"
$Route=Join-Path $Root "backend\app\api\routes\digital_well_twins.py"
$Main=Join-Path $Root "backend\app\main.py"
$Api=Join-Path $Root "frontend\src\features\platform\platformApi.ts"
$Panel=Join-Path $Root "frontend\src\features\platform\DigitalWellTwinPanel.tsx"
$Dash=Join-Path $Root "frontend\src\features\dashboard\DashboardPage.tsx"
foreach($p in @($Main,$Api,$Dash)){if(!(Test-Path $p)){throw "Missing baseline file: $p"}}
New-Item -ItemType Directory $Backup -Force|Out-Null
foreach($p in @($Main,$Api,$Dash)){Copy-Item $p (Join-Path $Backup ([IO.Path]::GetFileName($p))) -Force}
if(Test-Path $Route){Copy-Item $Route (Join-Path $Backup "digital_well_twins.py") -Force}
if(Test-Path $Panel){Copy-Item $Panel (Join-Path $Backup "DigitalWellTwinPanel.tsx") -Force}
function Put([string]$p,[string]$v){[IO.File]::WriteAllText($p,$v,(New-Object Text.UTF8Encoding($false)))}

Write-Host "[1/7] Persistent Digital Well Twin API" -ForegroundColor Cyan
Put $Route @'
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.core.rbac import require_roles

router=APIRouter()
READ=("admin","administrator","operator","engineer","geoscientist","petrophysicist","viewer")
WRITE=("admin","administrator","operator","engineer","geoscientist","petrophysicist")
DATA=Path(__file__).resolve().parents[3]/"data"; DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/"digital_well_twins.db"
def now(): return datetime.now(timezone.utc).isoformat()
def db():
 c=sqlite3.connect(DB,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row
 c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON")
 c.executescript("""
 CREATE TABLE IF NOT EXISTS digital_well_twins(
 twin_id TEXT PRIMARY KEY,name TEXT NOT NULL,asset_id TEXT,well_id TEXT NOT NULL,
 dataset_id TEXT NOT NULL,field_name TEXT,source_mode TEXT NOT NULL,status TEXT NOT NULL,
 curve_mapping_json TEXT NOT NULL,connector_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS twin_observations(
 observation_id TEXT PRIMARY KEY,twin_id TEXT NOT NULL,sequence INTEGER NOT NULL,depth REAL,
 observed_at TEXT NOT NULL,logs_json TEXT NOT NULL,state_json TEXT NOT NULL,alerts_json TEXT NOT NULL,
 FOREIGN KEY(twin_id) REFERENCES digital_well_twins(twin_id) ON DELETE CASCADE);
 CREATE INDEX IF NOT EXISTS ix_twin_obs ON twin_observations(twin_id,sequence);
 """); return c
class TwinCreate(BaseModel):
 twin_id:str=Field(min_length=2,max_length=100); name:str=Field(min_length=2,max_length=200)
 asset_id:str|None=None; well_id:str=Field(min_length=1); dataset_id:str=Field(min_length=1)
 field:str|None=None; source_mode:str="historical_replay"; curve_mapping:dict[str,str]=Field(default_factory=dict)
class Observation(BaseModel):
 sequence:int=Field(ge=0); depth:float|None=None; logs:dict[str,Any]=Field(default_factory=dict)
 state:dict[str,Any]=Field(default_factory=dict); alerts:list[str]=Field(default_factory=list); snapshot:bool=False
def unpack(r):
 x=dict(r); x["curve_mapping"]=json.loads(x.pop("curve_mapping_json")); x["connectors"]=json.loads(x.pop("connector_json")); x["field"]=x.pop("field_name"); x["asset_type"]="well"; return x
@router.get("")
def listing(_:dict=Depends(require_roles(*READ))):
 with db() as c: rows=c.execute("SELECT * FROM digital_well_twins ORDER BY updated_at DESC").fetchall()
 return [unpack(r) for r in rows]
@router.post("",status_code=status.HTTP_201_CREATED)
def create(p:TwinCreate,_:dict=Depends(require_roles(*WRITE))):
 t=now(); connectors={"simulation":{"status":"ready","protocol":"internal_replay"},"rest":{"status":"ready"},"websocket":{"status":"ready"},"mqtt":{"status":"not_configured"},"opc_ua":{"status":"not_configured"},"witsml":{"status":"not_configured"},"scada":{"status":"not_configured"}}
 try:
  with db() as c:c.execute("INSERT INTO digital_well_twins VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(p.twin_id.strip(),p.name.strip(),p.asset_id,p.well_id.strip(),p.dataset_id.strip(),p.field,p.source_mode,"ready",json.dumps(p.curve_mapping),json.dumps(connectors),t,t))
 except sqlite3.IntegrityError as e: raise HTTPException(409,"A twin with this ID already exists.") from e
 return one(p.twin_id,_)
@router.get("/{twin_id}")
def one(twin_id:str,_:dict=Depends(require_roles(*READ))):
 with db() as c:r=c.execute("SELECT * FROM digital_well_twins WHERE twin_id=?",(twin_id,)).fetchone()
 if not r: raise HTTPException(404,"Digital well twin not found.")
 return unpack(r)
@router.delete("/{twin_id}",status_code=204)
def remove(twin_id:str,_:dict=Depends(require_roles(*WRITE))):
 with db() as c:n=c.execute("DELETE FROM digital_well_twins WHERE twin_id=?",(twin_id,)).rowcount
 if not n: raise HTTPException(404,"Digital well twin not found.")
@router.post("/{twin_id}/observations",status_code=201)
def observe(twin_id:str,p:Observation,_:dict=Depends(require_roles(*WRITE))):
 one(twin_id,_); oid="obs-"+uuid4().hex[:16]; t=now()
 with db() as c:
  c.execute("INSERT INTO twin_observations VALUES(?,?,?,?,?,?,?,?)",(oid,twin_id,p.sequence,p.depth,t,json.dumps(p.logs),json.dumps(p.state),json.dumps(p.alerts)))
  c.execute("UPDATE digital_well_twins SET status='streaming',updated_at=? WHERE twin_id=?",(t,twin_id))
 return {"observation_id":oid,"sequence":p.sequence,"depth":p.depth,"observed_at":t}
@router.get("/{twin_id}/state")
def state(twin_id:str,_:dict=Depends(require_roles(*READ))):
 twin=one(twin_id,_)
 with db() as c:r=c.execute("SELECT * FROM twin_observations WHERE twin_id=? ORDER BY sequence DESC,observed_at DESC LIMIT 1",(twin_id,)).fetchone()
 if not r:return {"twin":twin,"observation":None,"state":{},"alerts":[]}
 return {"twin":twin,"observation":{"sequence":r["sequence"],"depth":r["depth"],"logs":json.loads(r["logs_json"]),"observed_at":r["observed_at"]},"state":json.loads(r["state_json"]),"alerts":json.loads(r["alerts_json"])}
@router.get("/{twin_id}/history")
def history(twin_id:str,limit:int=Query(500,ge=1,le=2000),_:dict=Depends(require_roles(*READ))):
 one(twin_id,_)
 with db() as c:rows=c.execute("SELECT * FROM twin_observations WHERE twin_id=? ORDER BY sequence DESC LIMIT ?",(twin_id,limit)).fetchall()
 rec=[{"sequence":r["sequence"],"depth":r["depth"],"observed_at":r["observed_at"],"logs":json.loads(r["logs_json"]),"state":json.loads(r["state_json"]),"alerts":json.loads(r["alerts_json"])} for r in reversed(rows)]
 return {"twin_id":twin_id,"count":len(rec),"records":rec}
@router.get("/{twin_id}/connectors")
def connectors(twin_id:str,_:dict=Depends(require_roles(*READ))):
 t=one(twin_id,_); return {"twin_id":twin_id,"connectors":t["connectors"]}
'@

Write-Host "[2/7] Route registration" -ForegroundColor Cyan
$m=[IO.File]::ReadAllText($Main)
if(!$m.Contains('"digital_well_twins"')){
 $hit=[regex]::Match($m,'(?ms)^(\s*)"twins"\s*:\s*\{.*?^\1\},')
 if($hit.Success){$i=$hit.Groups[1].Value;$e="`r`n${i}`"digital_well_twins`": {`r`n${i}    `"prefix`": `"/api/v1/digital-well-twins`",`r`n${i}    `"required`": true,`r`n${i}},";$m=$m.Insert($hit.Index+$hit.Length,$e)}
 else{$hit=[regex]::Match($m,'(?m)^(\s*)\("twins"\s*,.*$');if($hit.Success){$i=$hit.Groups[1].Value;$m=$m.Insert($hit.Index+$hit.Length+2,"${i}(`"digital_well_twins`", `"/api/v1/digital-well-twins`", True),`r`n")}else{throw "Could not locate route registry."}}
 Put $Main $m
}

Write-Host "[3/7] Frontend API" -ForegroundColor Cyan
$a=[IO.File]::ReadAllText($Api)
if(!$a.Contains("export interface DigitalWellTwin")){
$a+=@'

export interface DigitalWellTwin{twin_id:string;name:string;asset_type:"well";asset_id?:string|null;well_id:string;dataset_id:string;field?:string|null;source_mode:string;status:string;curve_mapping:Record<string,string>;connectors:Record<string,{status:string;protocol?:string}>;created_at:string;updated_at:string}
export const fetchDigitalWellTwins=()=>apiRequest<DigitalWellTwin[]>("/digital-well-twins");
export const createDigitalWellTwin=(p:{twin_id:string;name:string;asset_id?:string|null;well_id:string;dataset_id:string;field?:string|null;source_mode:string;curve_mapping:Record<string,string>})=>apiRequest<DigitalWellTwin>("/digital-well-twins",{method:"POST",body:JSON.stringify(p)});
export const deleteDigitalWellTwin=(id:string)=>apiRequest<void>(`/digital-well-twins/${encodeURIComponent(id)}`,{method:"DELETE"});
export const ingestDigitalTwinObservation=(id:string,p:Record<string,unknown>)=>apiRequest(`/digital-well-twins/${encodeURIComponent(id)}/observations`,{method:"POST",body:JSON.stringify(p)});
export const fetchDigitalTwinState=(id:string)=>apiRequest<{twin:DigitalWellTwin;observation:any;state:Record<string,any>;alerts:string[]}>(`/digital-well-twins/${encodeURIComponent(id)}/state`);
export const fetchDigitalTwinHistory=(id:string)=>apiRequest<{count:number;records:any[]}>(`/digital-well-twins/${encodeURIComponent(id)}/history`);
'@;Put $Api $a}

Write-Host "[4/7] Dynamic 3D workspace" -ForegroundColor Cyan
Put $Panel @'
import {FormEvent,useEffect,useRef,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Box,Button,Chip,Dialog,DialogActions,DialogContent,DialogTitle,FormControl,Grid,InputLabel,LinearProgress,MenuItem,Paper,Select,Slider,Stack,Tab,Tabs,TextField,Typography} from "@mui/material";
import {Activity,Box as Cube,Database,Gauge,Pause,Play,Plus,Radio,RefreshCw,RotateCcw,Save,Trash2,Waves} from "lucide-react";
import {SafePlot} from "../../components/SafePlot";
import {createDigitalWellTwin,deleteDigitalWellTwin,fetchAssets,fetchDatasets,fetchDigitalTwinHistory,fetchDigitalTwinState,fetchDigitalWellTwins,fetchReplay,ingestDigitalTwinObservation} from "./platformApi";
type E={sequence:number;depth:number;logs:Record<string,number>;prediction:Record<string,string|number>;alerts:string[]};
const speeds=[1000,500,250,100],num=(v:unknown,f=0)=>Number.isFinite(Number(v))?Number(v):f,pct=(v:unknown)=>`${(num(v)*100).toFixed(1)}%`,slug=(v:string)=>v.trim().toUpperCase().replace(/[^A-Z0-9]+/g,"-").replace(/^-|-$/g,"");
const state=(e?:E)=>e?{lithology:String(e.prediction.lithology??"Unknown"),porosity:num(e.prediction.porosity),permeability:num(e.prediction.permeability??e.prediction.permeability_md),water_saturation:num(e.prediction.water_saturation),hydrocarbon_probability:num(e.prediction.hydrocarbon_probability),pay_flag:String(e.prediction.pay_flag??"Non-pay"),anomaly_score:e.alerts.length?.8:.05,pressure:num(e.logs.pressure,e.depth*.0105),temperature:num(e.logs.temperature,25+e.depth*.025),flow_rate:num(e.logs.flow_rate)}:{};
function Well3D({events,index,property}:{events:E[];index:number;property:string}){
 const v=events.slice(0,index+1),z=v.map(e=>-e.depth),x=v.map((_e,i)=>Math.sin(i/25)*12),y=v.map((_e,i)=>Math.cos(i/31)*8);
 const val=v.map(e=>property==="gamma_ray"?num(e.logs.gr):num((state(e) as any)[property]));
 const traces:any[]=[{type:"scatter3d",mode:"lines+markers",x,y,z,line:{width:8,color:val,colorscale:"Viridis",colorbar:{title:property.replace(/_/g," ")}},marker:{size:5,color:val,colorscale:"Viridis",opacity:.72},text:v.map(e=>`Depth ${e.depth.toFixed(1)} m<br>${property}: ${property==="gamma_ray"?num(e.logs.gr).toFixed(3):num((state(e) as any)[property]).toFixed(3)}<br>${String(e.prediction.lithology??"")}`),hovertemplate:"%{text}<extra></extra>"}];
 if(v.length)traces.push({type:"scatter3d",mode:"markers",x:[x.at(-1)],y:[y.at(-1)],z:[z.at(-1)],marker:{size:13,symbol:"diamond",color:"#fff",line:{width:4,color:"#ff9800"}},name:"Live depth"});
 return <SafePlot data={traces} layout={{autosize:true,height:570,margin:{l:0,r:0,t:38,b:0},showlegend:false,paper_bgcolor:"rgba(0,0,0,0)",scene:{bgcolor:"rgba(0,0,0,0)",aspectmode:"manual",aspectratio:{x:.55,y:.55,z:2.2},xaxis:{title:"East offset (m)"},yaxis:{title:"North offset (m)"},zaxis:{title:"Depth (m)"}},title:{text:"Dynamic 3D wellbore and property envelope",font:{size:15}}}} config={{responsive:true,displaylogo:false,scrollZoom:true}}/>;
}
export function DigitalWellTwinPanel(){
 const qc=useQueryClient(),[tab,setTab]=useState(0),[selected,setSelected]=useState(""),[open,setOpen]=useState(false),[dataset,setDataset]=useState(""),[asset,setAsset]=useState(""),[id,setId]=useState(""),[name,setName]=useState(""),[well,setWell]=useState(""),[field,setField]=useState(""),[i,setI]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[property,setProperty]=useState("porosity");const persisted=useRef(-1);
 const twins=useQuery({queryKey:["digital-well-twins"],queryFn:fetchDigitalWellTwins,retry:3}),datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets,retry:3}),assets=useQuery({queryKey:["assets"],queryFn:fetchAssets,retry:3});
 const activeId=selected||twins.data?.[0]?.twin_id||"",active=twins.data?.find(t=>t.twin_id===activeId);
 const replay=useQuery({queryKey:["digital-well-twin","replay",active?.dataset_id],queryFn:()=>fetchReplay(active!.dataset_id),enabled:!!active?.dataset_id,staleTime:60000});
 const live=useQuery({queryKey:["digital-well-twin","state",activeId],queryFn:()=>fetchDigitalTwinState(activeId),enabled:!!activeId}),history=useQuery({queryKey:["digital-well-twin","history",activeId],queryFn:()=>fetchDigitalTwinHistory(activeId),enabled:!!activeId});
 const events=(replay.data?.events??[]) as E[],e=events[Math.min(i,Math.max(0,events.length-1))],s=state(e) as any;
 useEffect(()=>{if(!selected&&twins.data?.length)setSelected(twins.data[0].twin_id)},[selected,twins.data]);
 useEffect(()=>{setI(0);setPlaying(false);persisted.current=-1},[activeId]);
 useEffect(()=>{if(!playing||events.length<2)return;const t=setInterval(()=>setI(v=>v>=events.length-1?(setPlaying(false),events.length-1):v+1),speeds[speed]);return()=>clearInterval(t)},[playing,events.length,speed]);
 useEffect(()=>{if(!activeId||!e||persisted.current===i||(i%10&&i!==events.length-1))return;persisted.current=i;void ingestDigitalTwinObservation(activeId,{sequence:e.sequence,depth:e.depth,logs:e.logs,state:s,alerts:e.alerts,snapshot:i%50===0}).then(()=>{void live.refetch();void history.refetch()}).catch(()=>undefined)},[activeId,e,i]);
 const create=useMutation({mutationFn:()=>createDigitalWellTwin({twin_id:id,name,asset_id:asset||null,well_id:well,dataset_id:dataset,field:field||null,source_mode:"historical_replay",curve_mapping:{depth:"AUTO",gamma_ray:"AUTO",resistivity:"AUTO",density:"AUTO",neutron:"AUTO",sonic:"AUTO"}}),onSuccess:async t=>{setOpen(false);setSelected(t.twin_id);await qc.invalidateQueries({queryKey:["digital-well-twins"]})}});
 const remove=useMutation({mutationFn:()=>deleteDigitalWellTwin(activeId),onSuccess:async()=>{setSelected("");await qc.invalidateQueries({queryKey:["digital-well-twins"]})}});
 const choose=(v:string)=>{setDataset(v);const d=datasets.data?.find(x=>x.dataset_id===v),a=assets.data?.find(x=>x.dataset_id===v),w=a?.well||d?.well_name||d?.name||"WELL";setAsset(a?.asset_id??"");setWell(w);setField(a?.field||d?.field_name||"");setId(`${slug(w)}-TWIN`);setName(`${w} Digital Well Twin`)};
 const submit=(x:FormEvent)=>{x.preventDefault();if(dataset&&id&&name&&well)create.mutate()};
 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4}}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Box><Chip label="Living virtual well" className="hero-chip"/><Typography variant="h4" mt={1.2} fontWeight={900}>Digital Well Twin</Typography><Typography mt={1}>A persistent, continuously updated well model combining replay or sensor feeds, petrophysics, AI inference and a dynamic 3D depth-property view.</Typography></Box><Stack direction="row" gap={1} alignItems="center"><Chip icon={<Radio size={15}/>} color={playing?"success":"default"} label={playing?"Simulation live":"Twin ready"}/><Button startIcon={<RefreshCw/>} onClick={()=>void twins.refetch()}>Refresh</Button><Button variant="contained" startIcon={<Plus/>} onClick={()=>setOpen(true)}>Create well twin</Button></Stack></Stack></Paper>
  {(twins.isLoading||datasets.isLoading)&&<LinearProgress/>}{(twins.isError||datasets.isError)&&<Alert severity="error">Twin services could not initialise. Confirm authentication and backend health.</Alert>}
  <Paper variant="outlined" sx={{p:2}}><Grid container spacing={2} alignItems="center"><Grid item xs={12} md={5}><FormControl fullWidth><InputLabel>Digital well twin</InputLabel><Select label="Digital well twin" value={activeId} onChange={x=>setSelected(x.target.value)}>{(twins.data??[]).map(t=><MenuItem key={t.twin_id} value={t.twin_id}>{t.name} · {t.well_id}</MenuItem>)}</Select></FormControl></Grid><Grid item xs={12} md={3}><FormControl fullWidth><InputLabel>3D property</InputLabel><Select label="3D property" value={property} onChange={x=>setProperty(x.target.value)}>{["porosity","water_saturation","hydrocarbon_probability","permeability","gamma_ray","anomaly_score"].map(p=><MenuItem key={p} value={p}>{p.replace(/_/g," ")}</MenuItem>)}</Select></FormControl></Grid><Grid item xs={12} md={4}><Stack direction="row" gap={1}><Button fullWidth variant="contained" disabled={!events.length} startIcon={playing?<Pause/>:<Play/>} onClick={()=>setPlaying(v=>!v)}>{playing?"Pause":"Start simulation"}</Button><Button startIcon={<RotateCcw/>} onClick={()=>{setI(0);setPlaying(false)}}>Reset</Button><Button color="error" startIcon={<Trash2/>} disabled={!activeId} onClick={()=>remove.mutate()}>Delete</Button></Stack></Grid></Grid></Paper>
  {!active?<Alert severity="info">Create a well twin from a registered dataset. Creation is form-driven and does not depend on Developer Tools, focus or window resizing.</Alert>:<>
   <Grid container spacing={2}>{[["Depth",e?`${e.depth.toFixed(1)} m`:"—",<Waves/>],["Porosity",e?pct(s.porosity):"—",<Gauge/>],["Water saturation",e?pct(s.water_saturation):"—",<Activity/>],["Hydrocarbon",e?pct(s.hydrocarbon_probability):"—",<Database/>],["Pressure",e?`${num(s.pressure).toFixed(1)} MPa`:"—",<Gauge/>],["Temperature",e?`${num(s.temperature).toFixed(1)} °C`:"—",<Activity/>]].map(([l,v,ic])=><Grid item xs={6} md={2} key={String(l)}><Paper variant="outlined" sx={{p:2,height:"100%"}}><Stack direction="row" gap={1}>{ic}<Typography variant="caption">{l}</Typography></Stack><Typography variant="h6" mt={1}>{v}</Typography></Paper></Grid>)}</Grid>
   <Paper variant="outlined"><Tabs value={tab} onChange={(_e,v)=>setTab(v)} variant="scrollable"><Tab label="3D Live Twin"/><Tab label="Live State"/><Tab label="Hybrid Models"/><Tab label="Predictions"/><Tab label="Maintenance & Alerts"/><Tab label="Connectors"/></Tabs></Paper>
   {tab===0&&<Stack spacing={2}><Paper variant="outlined" sx={{p:1}}>{events.length?<Well3D events={events} index={i} property={property}/>:<Alert severity="info">No replay states are available.</Alert>}</Paper><Paper variant="outlined" sx={{p:2}}><Stack direction={{xs:"column",md:"row"}} gap={2} alignItems="center"><Button variant="contained" disabled={!events.length} startIcon={playing?<Pause/>:<Play/>} onClick={()=>setPlaying(v=>!v)}>{playing?"Pause":"Play"}</Button><Slider value={i} min={0} max={Math.max(0,events.length-1)} onChange={(_e,v)=>setI(Number(v))} sx={{flex:1}}/><FormControl sx={{minWidth:120}}><InputLabel>Speed</InputLabel><Select label="Speed" value={speed} onChange={x=>setSpeed(Number(x.target.value))}>{["0.5×","1×","2×","5×"].map((x,k)=><MenuItem value={k} key={x}>{x}</MenuItem>)}</Select></FormControl></Stack></Paper></Stack>}
   {tab===1&&<Grid container spacing={2}><Grid item xs={12} md={5}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Current state</Typography>{Object.entries(s).map(([k,v])=><Stack direction="row" justifyContent="space-between" mt={1} key={k}><Typography color="text.secondary">{k.replace(/_/g," ")}</Typography><Typography fontWeight={700}>{typeof v==="number"?v.toFixed(4):String(v)}</Typography></Stack>)}</Paper></Grid><Grid item xs={12} md={7}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Incoming measurements</Typography><Grid container spacing={2} mt={.5}>{Object.entries(e?.logs??{}).map(([k,v])=><Grid item xs={6} md={4} key={k}><Typography variant="caption">{k.toUpperCase()}</Typography><Typography fontWeight={800}>{num(v).toFixed(3)}</Typography></Grid>)}</Grid></Paper></Grid></Grid>}
   {tab===2&&<Grid container spacing={2}>{[["Physics layer","Porosity, saturation, permeability and depth-derived pressure/temperature baselines."],["AI layer","GRU live inference, BiGRU replay, lithology, anomaly and property prediction."],["Hybrid reconciliation","Shared state with provenance, confidence and engineering thresholds."],["Edge execution","CPU-first deployment, offline operation and queued synchronisation."]].map(([t,d])=><Grid item xs={12} md={6} key={t}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="h6">{t}</Typography><Typography color="text.secondary" mt={1}>{d}</Typography><Chip color="success" size="small" sx={{mt:2}} label="Connected architecture"/></Paper></Grid>)}</Grid>}
   {tab===3&&<Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Prediction and optimisation</Typography><Stack direction="row" gap={1} mt={2}><Chip label={String(s.lithology??"Unknown")}/><Chip color={s.pay_flag==="Pay"?"success":"default"} label={String(s.pay_flag??"Non-pay")}/><Chip label={`Permeability ${num(s.permeability).toFixed(1)} mD`}/></Stack><Alert severity={num(s.hydrocarbon_probability)>.6?"success":"info"} sx={{mt:2}}>{num(s.hydrocarbon_probability)>.6?"Prioritise this interval for reservoir review.":"Continue simulation; the current interval is below the hydrocarbon threshold."}</Alert></Paper>}
   {tab===4&&<Stack spacing={2}>{e?.alerts.length?e.alerts.map(x=><Alert severity="warning" key={x}>{x}</Alert>):<Alert severity="success">No active alert at this depth.</Alert>}<Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Maintenance rules</Typography><Typography color="text.secondary">Sensor drift, stuck values, missing curves, borehole enlargement, abnormal pressure or temperature, communication loss and model-confidence degradation.</Typography></Paper></Stack>}
   {tab===5&&<Grid container spacing={2}>{Object.entries(active.connectors??{}).map(([k,v])=><Grid item xs={12} sm={6} md={4} key={k}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6">{k.toUpperCase()}</Typography><Chip sx={{mt:1}} size="small" color={v.status==="ready"?"success":"default"} label={v.status.replace(/_/g," ")}/></Paper></Grid>)}</Grid>}
  </>}
  <Dialog open={open} onClose={()=>!create.isPending&&setOpen(false)} fullWidth maxWidth="md"><form onSubmit={submit}><DialogTitle>Create Digital Well Twin</DialogTitle><DialogContent><Stack spacing={2} mt={1}><Alert severity="info">Select a dataset. Historical replay will act as the simulated real-time sensor feed until field connectors are configured.</Alert><FormControl fullWidth required><InputLabel>Well dataset</InputLabel><Select label="Well dataset" value={dataset} onChange={x=>choose(x.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl><FormControl fullWidth><InputLabel>Registered asset</InputLabel><Select label="Registered asset" value={asset} onChange={x=>{setAsset(x.target.value);const a=assets.data?.find(v=>v.asset_id===x.target.value);if(a){setWell(a.well);setField(a.field)}}}><MenuItem value="">Dataset metadata</MenuItem>{(assets.data??[]).map(a=><MenuItem value={a.asset_id} key={a.asset_id}>{a.field} · {a.well}</MenuItem>)}</Select></FormControl><Grid container spacing={2}><Grid item xs={12} md={6}><TextField fullWidth required label="Twin ID" value={id} onChange={x=>setId(slug(x.target.value))}/></Grid><Grid item xs={12} md={6}><TextField fullWidth required label="Twin name" value={name} onChange={x=>setName(x.target.value)}/></Grid><Grid item xs={12} md={6}><TextField fullWidth required label="Well" value={well} onChange={x=>setWell(x.target.value)}/></Grid><Grid item xs={12} md={6}><TextField fullWidth label="Field" value={field} onChange={x=>setField(x.target.value)}/></Grid></Grid>{create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Creation failed."}</Alert>}</Stack></DialogContent><DialogActions><Button onClick={()=>setOpen(false)}>Cancel</Button><Button type="submit" variant="contained" startIcon={<Save/>} disabled={!dataset||!id||!name||!well||create.isPending}>{create.isPending?"Creating…":"Create persistent twin"}</Button></DialogActions></form></Dialog>
 </Stack>
}
'@

Write-Host "[5/7] Dashboard registration" -ForegroundColor Cyan
$d=[IO.File]::ReadAllText($Dash)
$anchor='const DigitalReplayPanel = lazy(() => import("../platform/DigitalReplayPanel").then((m) => ({ default: m.DigitalReplayPanel })));'
if(!$d.Contains("DigitalWellTwinPanel")){if(!$d.Contains($anchor)){throw "Dashboard import anchor missing"};$d=$d.Replace($anchor,$anchor+"`r`n"+'const DigitalWellTwinPanel = lazy(() => import("../platform/DigitalWellTwinPanel").then((m) => ({ default: m.DigitalWellTwinPanel })));')}
$tab='{ label: "Digital Replay", icon: <PlayCircle size={17} />, panel: <DigitalReplayPanel /> },'
if(!$d.Contains('{ label: "Digital Well Twin"')){if(!$d.Contains($tab)){throw "Dashboard tab anchor missing"};$d=$d.Replace($tab,'{ label: "Digital Well Twin", icon: <Cube size={17} />, panel: <DigitalWellTwinPanel /> },'+"`r`n    "+$tab)}
if(!$d.Contains("Cube,")){$d=$d.Replace("Boxes,","Boxes,`r`n  Box as Cube,")}
$d=$d.Replace('"digital-twin": "Interactive Logs"','"digital-twin": "Digital Well Twin"');Put $Dash $d

Write-Host "[6/7] Build and transactional rollback" -ForegroundColor Cyan
Set-Location $Root
docker compose config --quiet
docker compose build backend frontend
if($LASTEXITCODE-ne 0){
 Copy-Item (Join-Path $Backup "main.py") $Main -Force;Copy-Item (Join-Path $Backup "platformApi.ts") $Api -Force;Copy-Item (Join-Path $Backup "DashboardPage.tsx") $Dash -Force
 if(Test-Path (Join-Path $Backup "digital_well_twins.py")){Copy-Item (Join-Path $Backup "digital_well_twins.py") $Route -Force}else{Remove-Item $Route -Force -ErrorAction SilentlyContinue}
 if(Test-Path (Join-Path $Backup "DigitalWellTwinPanel.tsx")){Copy-Item (Join-Path $Backup "DigitalWellTwinPanel.tsx") $Panel -Force}else{Remove-Item $Panel -Force -ErrorAction SilentlyContinue}
 throw "Build failed; source rollback completed. Backup: $Backup"
}
docker compose up -d --force-recreate backend frontend
$ok=$false;for($x=0;$x-lt 30;$x++){try{$h=Invoke-RestMethod http://localhost:8000/health -TimeoutSec 5;if($h.status-eq"ok"){$ok=$true;break}}catch{};Start-Sleep 3}
if(!$ok){docker compose logs backend --tail 200;throw "Backend unhealthy. Backup: $Backup"}

Write-Host "[7/7] Route and compiled UI verification" -ForegroundColor Cyan
$o=Invoke-RestMethod http://localhost:8000/openapi.json -TimeoutSec 30
$paths=@($o.paths.PSObject.Properties.Name);$required=@("/api/v1/digital-well-twins","/api/v1/digital-well-twins/{twin_id}","/api/v1/digital-well-twins/{twin_id}/observations","/api/v1/digital-well-twins/{twin_id}/state","/api/v1/digital-well-twins/{twin_id}/history","/api/v1/digital-well-twins/{twin_id}/connectors");$missing=@($required|?{$paths-notcontains$_})
$marker=docker compose exec -T frontend sh -lc "grep -R -l 'Dynamic 3D wellbore and property envelope' /usr/share/nginx/html/assets 2>/dev/null || true" 2>&1
@("PHASE 6 DIGITAL WELL TWIN RESULT","Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')","Backup: $Backup","Missing paths: $($missing.Count)",($missing-join"`r`n"),"Compiled marker:",$marker,"Database: backend\data\digital_well_twins.db","$(docker compose ps -a|Out-String)")|Set-Content $Result -Encoding utf8
if($missing.Count){throw "Routes missing. Review $Result"}
if(-not(($marker-join"`n")-match"DigitalWellTwinPanel")){throw "3D UI marker missing. Review $Result"}
Write-Host "PHASE 6 DIGITAL WELL TWIN COMPLETED" -ForegroundColor Green
Write-Host "Result: $Result";Write-Host "Backup: $Backup";Write-Host "Close all browser tabs, reopen http://localhost:5173, and press Ctrl+Shift+R once." -ForegroundColor Yellow
