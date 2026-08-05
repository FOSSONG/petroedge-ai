import * as React from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Card, CardContent, Checkbox, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, Grid, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Slider, Stack, Tab, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Typography,
} from "@mui/material";
import { Cpu, Play, Radio, RefreshCw, Server, UploadCloud, WifiOff } from "lucide-react";
import * as PlotlyModule from "plotly.js-dist-min";
import { apiRequest } from "../../api/http";
import { fetchDatasets } from "./platformApi";

type LocalPlotProps = { data:any[]; layout?:Record<string,any>; config?:Record<string,any>; style?:React.CSSProperties; className?:string; useResizeHandler?:boolean; };
const PlotlyRuntime=(PlotlyModule as any).default?.default ?? (PlotlyModule as any).default ?? PlotlyModule;
function Plot({data,layout={},config={},style,className}:LocalPlotProps){
 const containerRef=React.useRef<HTMLDivElement|null>(null);
 React.useEffect(()=>{const container=containerRef.current;if(!container||typeof PlotlyRuntime?.react!=="function"){console.error("Plotly runtime could not be initialised.");return;}Promise.resolve(PlotlyRuntime.react(container,data,layout,{responsive:true,displaylogo:false,...config})).catch((error:unknown)=>console.error("Plotly chart rendering failed:",error));},[data,layout,config]);
 React.useEffect(()=>()=>{const container=containerRef.current;if(container&&typeof PlotlyRuntime?.purge==="function")PlotlyRuntime.purge(container);},[]);
 return <div ref={containerRef} className={className} style={{width:"100%",minHeight:420,...style}}/>;
}

type Device = { device_id:string; name:string; status:string; architecture:string; cpu_cores:number; memory_mb:number; storage_free_mb:number; operating_system:string; network_state:string; deployed_model_id?:string|null; model_version?:string|null; inference_count:number; average_latency_ms:number; pending_sync_count:number; };
type EdgeResult = { row_index:number; depth:number; gr:number; rt:number; rhob?:number|null; nphi?:number|null; vsh:number; porosity:number; effective_porosity:number; permeability_md:number; water_saturation:number; water_probability:number; oil_probability:number; gas_probability:number; hydrocarbon_probability:number; anomaly_score:number; anomaly:boolean; pay_zone:boolean; reservoir_class:string; fluid_class:string; interpretation:string; latency_ms:number; };
type PlotPoint = { depth:number; gr:number; rt:number; reservoir_class:string; pay_zone:boolean; };
type EdgeRun = { run_id:string; device_id:string; model_id:string; model_kind:string; workflow:string; status:string; records_processed:number; predictions_generated:number; skipped_rows?:number; average_latency_ms:number; runtime:string; fallback:boolean; pay_zone_count?:number; anomaly_count?:number; completed_at:string; };
type ReplayJob = { job_id:string; device_id:string; status:"queued"|"running"|"completed"|"failed"; predictions_completed:number; total_predictions:number; rows_examined?:number; skipped_rows?:number; progress_percent:number; current_depth?:number; latest_result?:EdgeResult; latest_latency_ms?:number; runtime?:string|null; fallback?:boolean|null; recent_results?:EdgeResult[]; plot_points?:PlotPoint[]; pay_zone_count?:number; anomaly_count?:number; error?:string; run?:EdgeRun; };
type Dashboard = { summary:{registered_devices:number;online_devices:number;deployed_models:number;total_inferences:number;pending_sync_items:number;average_latency_ms:number}; devices:Device[]; deployments:Array<Record<string,unknown>>; recent_runs:EdgeRun[]; };
type Capabilities = { edge_ready:boolean; architectures:string[]; accelerators:string[]; connectors:string[]; temporal_models:string[]; workflows:string[]; release:string; };
type LiveInferenceStatus = {
  physics_ready:boolean;
  trained_gru_installed:boolean;
  trained_gru_path:string;
  live_demo_fallback_allowed:boolean;
  fusion_policy:string;
  bigru_live_allowed:boolean;
};


const fetchCapabilities=()=>apiRequest<Capabilities>("/edge/capabilities");
const fetchLiveInferenceStatus=()=>apiRequest<LiveInferenceStatus>("/streaming/edge/inference/status");
const fetchDashboard=()=>apiRequest<Dashboard>("/edge/dashboard");
const registerDevice=(payload:Record<string,unknown>)=>apiRequest<Device>("/edge/devices",{method:"POST",body:JSON.stringify(payload)});
const deployModel=(deviceId:string,payload:Record<string,unknown>)=>apiRequest(`/edge/devices/${deviceId}/deployments`,{method:"POST",body:JSON.stringify(payload)});
const startReplay=(deviceId:string,payload:Record<string,unknown>)=>apiRequest<ReplayJob>(`/edge/devices/${deviceId}/replay/start`,{method:"POST",body:JSON.stringify(payload)});
const fetchReplayJob=(jobId:string)=>apiRequest<ReplayJob>(`/edge/replay/jobs/${jobId}`);
const syncDevice=(deviceId:string)=>apiRequest(`/edge/devices/${deviceId}/sync`,{method:"POST"});
const titleCase=(value:string)=>value.replace(/_/g," ").replace(/\b\w/g,(letter)=>letter.toUpperCase());
const pct=(value:number|undefined)=>`${((value??0)*100).toFixed(1)}%`;

function MetricCard({label,value,icon}:{label:string;value:string|number;icon:JSX.Element}) { return <Card variant="outlined" sx={{height:"100%"}}><CardContent><Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Typography color="text.secondary" variant="body2">{label}</Typography><Typography variant="h4" fontWeight={900}>{value}</Typography></Box>{icon}</Stack></CardContent></Card>; }

export function EdgeComputingPanel(){
  const queryClient=useQueryClient();
  const [tab,setTab]=useState(0); const [datasetId,setDatasetId]=useState(""); const [deviceId,setDeviceId]=useState("edge-demo-01");
  const [modelKind,setModelKind]=useState("gru"); const [workflow,setWorkflow]=useState("digital_twin_state"); const [offline,setOffline]=useState(false);
  const [intervalMs,setIntervalMs]=useState(100); const [registerOpen,setRegisterOpen]=useState(false); const [replayJobId,setReplayJobId]=useState(""); const [deviceName,setDeviceName]=useState("Field Edge Node");
  const capabilities=useQuery({queryKey:["edge","capabilities"],queryFn:fetchCapabilities});
  const liveInference=useQuery({queryKey:["edge","live-inference-status"],queryFn:fetchLiveInferenceStatus,refetchInterval:10000});
  const dashboard=useQuery({queryKey:["edge","dashboard"],queryFn:fetchDashboard,refetchInterval:10000});
  const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
  const activeDataset=datasetId||datasets.data?.[0]?.dataset_id||"";
  const invalidate=async()=>queryClient.invalidateQueries({queryKey:["edge","dashboard"]});
  const register=useMutation({mutationFn:()=>registerDevice({name:deviceName,architecture:"linux/amd64",cpu_cores:4,memory_mb:2048,storage_free_mb:8192}),onSuccess:async(device)=>{setDeviceId(device.device_id);setRegisterOpen(false);await invalidate();}});
  const deploy=useMutation({mutationFn:()=>deployModel(deviceId,{model_kind:modelKind,workflow,version:"2.2.0"}),onSuccess:invalidate});
  const replay=useMutation({mutationFn:()=>startReplay(deviceId,{dataset_id:activeDataset,model_kind:modelKind,workflow,offline,interval_ms:intervalMs}),onSuccess:(job)=>setReplayJobId(job.job_id)});
  const replayStatus=useQuery({queryKey:["edge","replay-job",replayJobId],queryFn:()=>fetchReplayJob(replayJobId),enabled:Boolean(replayJobId),refetchInterval:(query)=>["completed","failed"].includes(query.state.data?.status??"")?false:300});
  useEffect(()=>{if(replayStatus.data?.status==="completed")void invalidate();},[replayStatus.data?.status]);
  const synchronise=useMutation({mutationFn:()=>syncDevice(deviceId),onSuccess:invalidate});
  const selectedDevice=dashboard.data?.devices.find(item=>item.device_id===deviceId)??dashboard.data?.devices[0]; const summary=dashboard.data?.summary;
  const liveRows=[...(replayStatus.data?.recent_results??[])].reverse(); const plotPoints=replayStatus.data?.plot_points??[];
  const reservoirPoints=useMemo(()=>plotPoints.filter(p=>p.reservoir_class==="Reservoir"),[plotPoints]);
  const nonReservoirPoints=useMemo(()=>plotPoints.filter(p=>p.reservoir_class!=="Reservoir"),[plotPoints]);

  return <Stack spacing={3}>
    <Paper className="hero-panel" sx={{p:3}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Stack direction="row" gap={1.5} alignItems="center"><Cpu/><Box><Typography variant="h4" fontWeight={900}>Edge Computing</Typography><Typography>Depth-indexed real-time petrophysical interpretation, edge replay and offline synchronisation.</Typography></Box></Stack><Stack direction="row" gap={1}><Chip color="success" label={`Release ${capabilities.data?.release??"2.2.0"}`}/><Button startIcon={<RefreshCw size={17}/>} onClick={()=>dashboard.refetch()}>Refresh</Button></Stack></Stack></Paper>
    <Paper variant="outlined" sx={{p:2.5}}>
      <Stack spacing={1.5}>
        <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={1}>
          <Box>
            <Typography variant="h6" fontWeight={900}>Live B2 inference status</Typography>
            <Typography variant="body2" color="text.secondary">Operational stream path: B1 quality gate → deterministic petrophysics → causal GRU when a validated ONNX artefact is installed → provenance-aware fusion.</Typography>
          </Box>
          <Stack direction="row" gap={1} flexWrap="wrap">
            <Chip color={liveInference.data?.physics_ready?"success":"error"} label={liveInference.data?.physics_ready?"Physics ready":"Physics unavailable"}/>
            <Chip color={liveInference.data?.trained_gru_installed?"success":"warning"} label={liveInference.data?.trained_gru_installed?"TRAINED_MODEL":"PHYSICS_ONLY"}/>
            <Chip color={liveInference.data?.live_demo_fallback_allowed?"error":"success"} label={liveInference.data?.live_demo_fallback_allowed?"Demo fallback enabled":"Live demo fallback blocked"}/>
          </Stack>
        </Stack>
        {liveInference.isLoading&&<LinearProgress/>}
        {liveInference.isError&&<Alert severity="warning">The B2 live inference status endpoint could not be loaded. Existing edge replay remains available, but live model provenance cannot be verified from this panel.</Alert>}
        {liveInference.data&&!liveInference.data.trained_gru_installed&&<Alert severity="warning">No validated causal GRU ONNX artefact is installed. Live B2 interpretation therefore remains in PHYSICS_ONLY mode. This is intentional: PetroEdge will not present deterministic demo fallback as trained AI.</Alert>}
        {liveInference.data?.trained_gru_installed&&<Alert severity="success">A trained causal GRU artefact is installed. Live streaming can enter TRAINED_MODEL mode after the causal warm-up window is satisfied.</Alert>}
        {liveInference.data&&<Grid container spacing={1.5}>
          <Grid item xs={12} md={4}><Paper variant="outlined" sx={{p:1.5,height:"100%"}}><Typography variant="caption" color="text.secondary">Fusion policy</Typography><Typography variant="body2" fontWeight={700}>{liveInference.data.fusion_policy}</Typography></Paper></Grid>
          <Grid item xs={12} md={4}><Paper variant="outlined" sx={{p:1.5,height:"100%"}}><Typography variant="caption" color="text.secondary">GRU artefact</Typography><Typography variant="body2" sx={{wordBreak:"break-all"}}>{liveInference.data.trained_gru_path}</Typography></Paper></Grid>
          <Grid item xs={12} md={4}><Paper variant="outlined" sx={{p:1.5,height:"100%"}}><Typography variant="caption" color="text.secondary">Live BiGRU</Typography><Typography variant="body2" fontWeight={700}>{liveInference.data.bigru_live_allowed?"Allowed":"Blocked — replay/historical only"}</Typography></Paper></Grid>
        </Grid>}
        <Alert severity="info">The “Rig-site replay” tab below is the existing historical/depth replay workflow. The status above reports the new B2 live-stream inference path and its actual model provenance.</Alert>
      </Stack>
    </Paper>
    {(dashboard.isLoading||capabilities.isLoading)&&<LinearProgress/>}{(dashboard.isError||capabilities.isError)&&<Alert severity="error">The Edge Computing API could not be loaded.</Alert>}
    <Grid container spacing={2}><Grid item xs={12} sm={6} md={2.4}><MetricCard label="Registered devices" value={summary?.registered_devices??0} icon={<Server/>}/></Grid><Grid item xs={12} sm={6} md={2.4}><MetricCard label="Online" value={summary?.online_devices??0} icon={<Radio/>}/></Grid><Grid item xs={12} sm={6} md={2.4}><MetricCard label="Models deployed" value={summary?.deployed_models??0} icon={<UploadCloud/>}/></Grid><Grid item xs={12} sm={6} md={2.4}><MetricCard label="Inference outputs" value={summary?.total_inferences??0} icon={<Cpu/>}/></Grid><Grid item xs={12} sm={6} md={2.4}><MetricCard label="Pending sync" value={summary?.pending_sync_items??0} icon={<WifiOff/>}/></Grid></Grid>
    <Paper variant="outlined"><Tabs value={tab} onChange={(_e,v)=>setTab(v)} variant="scrollable"><Tab label="Device dashboard"/><Tab label="Model deployment"/><Tab label="Rig-site replay"/><Tab label="Run history"/></Tabs></Paper>
    {tab===0&&<Stack spacing={2}><Stack direction="row" justifyContent="space-between"><Typography variant="h6">Registered edge devices</Typography><Button variant="contained" onClick={()=>setRegisterOpen(true)}>Register device</Button></Stack><Grid container spacing={2}>{(dashboard.data?.devices??[]).map(device=><Grid item xs={12} md={6} key={device.device_id}><Card variant="outlined" sx={{cursor:"pointer",borderColor:device.device_id===deviceId?"primary.main":"divider"}} onClick={()=>setDeviceId(device.device_id)}><CardContent><Stack direction="row" justifyContent="space-between"><Typography variant="h6">{device.name}</Typography><Chip size="small" color={device.status==="online"?"success":"default"} label={device.status}/></Stack><Typography variant="body2" color="text.secondary">{device.device_id} · {device.architecture}</Typography><Typography variant="body2" mt={1}>CPU {device.cpu_cores} cores · RAM {device.memory_mb} MB · Storage {device.storage_free_mb} MB · {device.average_latency_ms} ms</Typography></CardContent></Card></Grid>)}</Grid></Stack>}
    {tab===1&&<Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Typography variant="h6">Deploy a temporal model</Typography><FormControl fullWidth><InputLabel>Device</InputLabel><Select value={selectedDevice?.device_id??""} label="Device" onChange={e=>setDeviceId(e.target.value)}>{(dashboard.data?.devices??[]).map(d=><MenuItem key={d.device_id} value={d.device_id}>{d.name}</MenuItem>)}</Select></FormControl><Stack direction={{xs:"column",md:"row"}} gap={2}><FormControl fullWidth><InputLabel>Model</InputLabel><Select value={modelKind} label="Model" onChange={e=>setModelKind(e.target.value)}><MenuItem value="gru">GRU · causal/live</MenuItem><MenuItem value="bigru">BiGRU · replay/historical</MenuItem></Select></FormControl><FormControl fullWidth><InputLabel>Workflow</InputLabel><Select value={workflow} label="Workflow" onChange={e=>setWorkflow(e.target.value)}>{(capabilities.data?.workflows??[]).map(item=><MenuItem key={item} value={item}>{titleCase(item)}</MenuItem>)}</Select></FormControl></Stack><Alert severity="info">Until a validated multi-output ONNX model is installed, the replay uses explicit industry-standard petrophysical equations rather than an opaque synthetic score.</Alert><Button variant="contained" disabled={!deviceId||deploy.isPending} onClick={()=>deploy.mutate()}>Deploy model</Button></Stack></Paper>}
    {tab===2&&<Stack spacing={2}>
      <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Typography variant="h6">Real-time depth replay</Typography><FormControl fullWidth><InputLabel>Dataset</InputLabel><Select value={activeDataset} label="Dataset" onChange={e=>setDatasetId(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name} ({(d.row_count ?? 0).toLocaleString()} rows)</MenuItem>)}</Select></FormControl><FormControl fullWidth><InputLabel>Device</InputLabel><Select value={selectedDevice?.device_id??""} label="Device" onChange={e=>setDeviceId(e.target.value)}>{(dashboard.data?.devices??[]).map(d=><MenuItem key={d.device_id} value={d.device_id}>{d.name}</MenuItem>)}</Select></FormControl><Box><Typography gutterBottom>Simulation speed: {intervalMs===0?"Maximum":`${intervalMs} ms per depth row`}</Typography><Slider value={intervalMs} min={0} max={2000} step={25} marks={[{value:0,label:"Max"},{value:250,label:"Fast"},{value:1000,label:"Normal"},{value:2000,label:"Slow"}]} onChange={(_e,v)=>setIntervalMs(v as number)}/></Box><FormControlLabel control={<Checkbox checked={offline} onChange={e=>setOffline(e.target.checked)}/>} label="Simulate offline operation and queue results"/><Stack direction={{xs:"column",sm:"row"}} gap={1}><Button variant="contained" startIcon={<Play/>} disabled={!deviceId||!activeDataset||replay.isPending||["running","queued"].includes(replayStatus.data?.status??"")} onClick={()=>{setReplayJobId("");replay.mutate();}}>Start depth replay</Button><Button variant="outlined" startIcon={<UploadCloud/>} disabled={!deviceId||synchronise.isPending} onClick={()=>synchronise.mutate()}>Synchronise queued results</Button></Stack></Stack></Paper>
      {replayStatus.data&&<Paper variant="outlined" sx={{p:2}}><Stack spacing={1}><Stack direction="row" justifyContent="space-between"><Typography fontWeight={800}>Live petrophysical inference</Typography><Chip size="small" color={replayStatus.data.status==="completed"?"success":"info"} label={replayStatus.data.status}/></Stack><LinearProgress variant="determinate" value={replayStatus.data.progress_percent}/><Typography variant="body2">Examined {(replayStatus.data.rows_examined??0).toLocaleString()} of {(replayStatus.data.total_predictions||0).toLocaleString()} dataset rows · valid interpretations {replayStatus.data.predictions_completed.toLocaleString()} · skipped {(replayStatus.data.skipped_rows??0).toLocaleString()} · depth {replayStatus.data.current_depth??"—"}</Typography>{replayStatus.data.latest_result&&<Stack direction="row" gap={1} flexWrap="wrap"><Chip label={`Porosity ${pct(replayStatus.data.latest_result.porosity)}`}/><Chip label={`Permeability ${replayStatus.data.latest_result.permeability_md} mD`}/><Chip label={`Sw ${pct(replayStatus.data.latest_result.water_saturation)}`}/><Chip label={`Oil ${pct(replayStatus.data.latest_result.oil_probability)}`}/><Chip label={`Gas ${pct(replayStatus.data.latest_result.gas_probability)}`}/><Chip label={`Water ${pct(replayStatus.data.latest_result.water_probability)}`}/><Chip color={replayStatus.data.latest_result.pay_zone?"success":"default"} label={replayStatus.data.latest_result.pay_zone?"Hydrocarbon pay":"Non-pay"}/><Chip color={replayStatus.data.latest_result.anomaly?"warning":"default"} label={`Anomaly ${pct(replayStatus.data.latest_result.anomaly_score)}`}/></Stack>}<Typography variant="body2" color="text.secondary">Runtime: {replayStatus.data.runtime??"initialising"} · latest calculation latency {replayStatus.data.latest_latency_ms??0} ms</Typography></Stack></Paper>}
      {plotPoints.length>0&&<Paper variant="outlined" sx={{p:2}}><Typography variant="h6">Live GR–RT reservoir discrimination with depth</Typography><Plot style={{width:"100%",height:520}} useResizeHandler data={[{x:reservoirPoints.map(p=>p.gr),y:reservoirPoints.map(p=>p.depth),customdata:reservoirPoints.map(p=>p.rt),mode:"markers",type:"scatter",name:"Reservoir",marker:{size:6},hovertemplate:"Depth %{y}<br>GR %{x}<br>RT %{customdata}<extra>Reservoir</extra>"},{x:nonReservoirPoints.map(p=>p.gr),y:nonReservoirPoints.map(p=>p.depth),customdata:nonReservoirPoints.map(p=>p.rt),mode:"markers",type:"scatter",name:"Non-reservoir",marker:{size:5},hovertemplate:"Depth %{y}<br>GR %{x}<br>RT %{customdata}<extra>Non-reservoir</extra>"}]} layout={{autosize:true,paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)",font:{color:"#cbd5e1"},xaxis:{title:"Gamma Ray (API)"},yaxis:{title:"Depth",autorange:"reversed"},legend:{orientation:"h"},margin:{l:70,r:30,t:30,b:60}}}/><Typography variant="caption" color="text.secondary">Every valid row is interpreted. For display performance, the live plot retains up to 1,200 representative points while the backend processes the complete dataset.</Typography></Paper>}
      {liveRows.length>0&&<TableContainer component={Paper} variant="outlined" sx={{maxHeight:520}}><Table stickyHeader size="small"><TableHead><TableRow>{["Depth","GR","RT","Porosity","Perm (mD)","Sw","Water","Oil","Gas","HC prob.","Anomaly","Reservoir","Pay zone","Interpretation"].map(h=><TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead><TableBody>{liveRows.map(r=><TableRow key={`${r.row_index}-${r.depth}`}><TableCell>{r.depth}</TableCell><TableCell>{r.gr}</TableCell><TableCell>{r.rt}</TableCell><TableCell>{pct(r.porosity)}</TableCell><TableCell>{r.permeability_md}</TableCell><TableCell>{pct(r.water_saturation)}</TableCell><TableCell>{pct(r.water_probability)}</TableCell><TableCell>{pct(r.oil_probability)}</TableCell><TableCell>{pct(r.gas_probability)}</TableCell><TableCell>{pct(r.hydrocarbon_probability)}</TableCell><TableCell>{pct(r.anomaly_score)}</TableCell><TableCell>{r.reservoir_class}</TableCell><TableCell>{r.pay_zone?"Yes":"No"}</TableCell><TableCell sx={{minWidth:300}}>{r.interpretation}</TableCell></TableRow>)}</TableBody></Table></TableContainer>}
      {replayStatus.data?.status==="completed"&&replayStatus.data.run&&<Alert severity="success">Run {replayStatus.data.run.run_id} processed {replayStatus.data.run.records_processed.toLocaleString()} rows and generated {replayStatus.data.run.predictions_generated.toLocaleString()} valid depth interpretations, including {replayStatus.data.run.pay_zone_count??0} pay-zone samples and {replayStatus.data.run.anomaly_count??0} anomalies. Runtime: {replayStatus.data.run.runtime}.</Alert>}{replayStatus.data?.status==="failed"&&<Alert severity="error">Replay failed: {replayStatus.data.error}</Alert>}
    </Stack>}
    {tab===3&&<Paper variant="outlined" sx={{p:3}}><Typography variant="h6" mb={2}>Recent edge inference runs</Typography><Stack spacing={1.5}>{(dashboard.data?.recent_runs??[]).map(run=><Paper key={run.run_id} variant="outlined" sx={{p:2}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between"><Box><Typography fontWeight={800}>{run.run_id}</Typography><Typography variant="body2" color="text.secondary">{run.model_id} · {titleCase(run.workflow)}</Typography></Box><Stack direction="row" gap={1} flexWrap="wrap"><Chip size="small" label={`${run.predictions_generated} interpretations`}/><Chip size="small" label={`${run.average_latency_ms} ms`}/><Chip size="small" label={run.runtime}/></Stack></Stack></Paper>)}</Stack></Paper>}
    <Dialog open={registerOpen} onClose={()=>setRegisterOpen(false)} fullWidth maxWidth="sm"><DialogTitle>Register edge device</DialogTitle><DialogContent><TextField autoFocus fullWidth margin="normal" label="Device name" value={deviceName} onChange={e=>setDeviceName(e.target.value)}/></DialogContent><DialogActions><Button onClick={()=>setRegisterOpen(false)}>Cancel</Button><Button variant="contained" disabled={!deviceName.trim()||register.isPending} onClick={()=>register.mutate()}>Register</Button></DialogActions></Dialog>
  </Stack>;
}
