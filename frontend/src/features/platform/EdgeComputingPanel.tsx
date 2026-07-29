import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Typography } from "@mui/material";
import { Cpu, Play } from "lucide-react";
import { apiRequest } from "../../api/http";
import { fetchDatasetPreview, fetchDatasets } from "./platformApi";

type Capabilities={edge_ready:boolean;architectures:string[];accelerators:string[];connectors:string[];temporal_models:string[];workflows:string[];policy:Record<string,string>};
type Prediction={model_id:string;model_kind?:string;workflow?:string;prediction?:unknown;latency_ms?:number;[key:string]:unknown};
const capabilities=()=>apiRequest<Capabilities>("/edge/capabilities");
const predict=(payload:Record<string,unknown>)=>apiRequest<Prediction>("/edge/temporal/predict",{method:"POST",body:JSON.stringify(payload)});
const n=(v:unknown)=>typeof v==="number"&&Number.isFinite(v)?v:null;
export function EdgeComputingPanel(){
 const caps=useQuery({queryKey:["edge","capabilities"],queryFn:capabilities}); const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [datasetId,setDatasetId]=useState(""); const [kind,setKind]=useState("GRU"); const [workflow,setWorkflow]=useState("digital_twin"); const active=datasetId||datasets.data?.[0]?.dataset_id||"";
 const preview=useQuery({queryKey:["edge","preview",active],queryFn:()=>fetchDatasetPreview(active),enabled:Boolean(active)});
 const matrix=useMemo(()=>{const rows=preview.data?.rows??[];return rows.map(row=>Object.values(row).map(n).filter((x):x is number=>x!==null).slice(0,8)).filter(r=>r.length>0).slice(0,64);},[preview.data]);
 const width=Math.min(...matrix.map(r=>r.length).filter(Boolean),8); const values=Number.isFinite(width)&&width>0?matrix.map(r=>r.slice(0,width)):[];
 const run=useMutation({mutationFn:()=>predict({model_kind:kind,workflow,execution_mode:kind==="GRU"?"live":"historical",values,window_size:Math.max(4,Math.min(32,values.length))})});
 return <Stack spacing={3}><Paper className="hero-panel" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center"><Cpu/><Box><Typography variant="h4" fontWeight={900}>Edge Computing</Typography><Typography>Dataset-driven GRU/BiGRU temporal inference for rig-site and offline workflows.</Typography></Box></Stack></Paper>
 {caps.isError&&<Alert severity="error">Edge capabilities could not be loaded.</Alert>}{caps.data&&<Stack direction="row" gap={1} flexWrap="wrap"><Chip color={caps.data.edge_ready?"success":"default"} label={caps.data.edge_ready?"Edge ready":"Not ready"}/>{caps.data.architectures.map(x=><Chip key={x} label={x}/>)}{caps.data.accelerators.map(x=><Chip key={x} label={x}/>)}</Stack>}
 <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><FormControl fullWidth><InputLabel>Dataset</InputLabel><Select value={active} label="Dataset" onChange={e=>setDatasetId(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl><Stack direction={{xs:"column",md:"row"}} gap={2}><FormControl fullWidth><InputLabel>Temporal model</InputLabel><Select value={kind} label="Temporal model" onChange={e=>setKind(e.target.value)}><MenuItem value="GRU">GRU · causal/live</MenuItem><MenuItem value="BiGRU">BiGRU · historical/batch</MenuItem></Select></FormControl><FormControl fullWidth><InputLabel>Workflow</InputLabel><Select value={workflow} label="Workflow" onChange={e=>setWorkflow(e.target.value)}>{(caps.data?.workflows??["digital_twin"]).map(x=><MenuItem key={x} value={x}>{x.replace(/_/g," ")}</MenuItem>)}</Select></FormControl></Stack><Typography color="text.secondary">{values.length} rows × {width||0} numeric features prepared internally. No editable JSON is required.</Typography><Button variant="contained" startIcon={<Play/>} disabled={values.length<4||run.isPending} onClick={()=>run.mutate()}>Run edge inference</Button></Stack></Paper>
 {run.isError&&<Alert severity="error">Inference failed. Ensure the selected dataset contains at least four rows with numeric log measurements.</Alert>}{run.data&&<Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Inference result</Typography><Box component="pre" sx={{whiteSpace:"pre-wrap",overflow:"auto",fontSize:13}}>{JSON.stringify(run.data,null,2)}</Box></Paper>}</Stack>;
}
