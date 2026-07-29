import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Card, CardContent, Chip, FormControl, Grid, InputLabel, LinearProgress, MenuItem, Select, Stack, Typography } from "@mui/material";
import { Activity, Cpu, Database, Play } from "lucide-react";
import { apiRequest } from "../../api/http";
import { fetchDatasetPreview, fetchDatasets } from "../platform/platformApi";

type Cap={edge_ready:boolean;architectures:string[];accelerators:string[];connectors:string[];temporal_models:string[];policy:Record<string,string>;workflows:string[]};
type Result=Record<string,unknown>;
const numeric=(v:unknown)=>typeof v==="number"?Number.isFinite(v):Number.isFinite(Number(v));
const pretty=(s:string)=>s.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
function Metric({label,value}:{label:string;value:unknown}){return <Box sx={{p:1.5,bgcolor:"grey.50",borderRadius:2}}><Typography variant="caption" color="text.secondary">{pretty(label)}</Typography><Typography fontWeight={800}>{typeof value==="number"?value.toLocaleString(undefined,{maximumFractionDigits:4}):String(value)}</Typography></Box>}
export function EdgeWorkspace(){
 const caps=useQuery({queryKey:["edge-capabilities"],queryFn:()=>apiRequest<Cap>("/edge/capabilities")});
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [datasetId,setDatasetId]=useState(""); const selectedId=datasetId||datasets.data?.[0]?.dataset_id||"";
 const preview=useQuery({queryKey:["platform","preview",selectedId,"edge"],queryFn:()=>fetchDatasetPreview(selectedId),enabled:Boolean(selectedId)});
 const [kind,setKind]=useState("gru"),[workflow,setWorkflow]=useState("digital_twin_state"),[mode,setMode]=useState("live"),[windowSize,setWindowSize]=useState(12),[result,setResult]=useState<Result|null>(null);
 const numericColumns=useMemo(()=>{const rows=preview.data?.rows??[];return (preview.data?.columns??[]).filter(c=>rows.some(r=>numeric(r[c])));},[preview.data]);
 const matrix=useMemo(()=>{const rows=preview.data?.rows??[];return rows.map(r=>numericColumns.map(c=>Number(r[c]))).filter(r=>r.every(Number.isFinite)).slice(0,1000);},[preview.data,numericColumns]);
 const run=useMutation({mutationFn:()=>apiRequest<Result>("/edge/temporal/predict",{method:"POST",body:JSON.stringify({model_kind:kind,workflow,execution_mode:mode,values:matrix,window_size:windowSize})}),onSuccess:setResult});
 const objectMetrics=result?Object.entries(result).filter(([,v])=>typeof v!=="object"):[];
 return <Stack spacing={2.5}>
  <Card className="feature-hero" variant="outlined"><CardContent><Typography variant="h4">Edge Temporal Inference</Typography><Typography sx={{mt:1}}>Run governed temporal models directly against an uploaded PetroEdge dataset. The feature matrix is assembled automatically from recognised numeric columns.</Typography></CardContent></Card>
  {(caps.isLoading||datasets.isLoading)&&<LinearProgress/>}{caps.isError&&<Alert severity="error">Unable to load edge capabilities.</Alert>}
  <Grid container spacing={2}><Grid item xs={12} lg={5}><Card variant="outlined"><CardContent><Stack spacing={2}>
   <Stack direction="row" gap={1} alignItems="center"><Database size={20}/><Typography variant="h6">Inference setup</Typography></Stack>
   <FormControl fullWidth><InputLabel>Uploaded dataset</InputLabel><Select label="Uploaded dataset" value={selectedId} onChange={e=>setDatasetId(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl>
   <FormControl fullWidth><InputLabel>Temporal model</InputLabel><Select label="Temporal model" value={kind} onChange={e=>setKind(e.target.value)}>{(caps.data?.temporal_models??["GRU","BiGRU"]).map(x=><MenuItem key={x} value={x.toLowerCase()}>{x}</MenuItem>)}</Select></FormControl>
   <FormControl fullWidth><InputLabel>Workflow</InputLabel><Select label="Workflow" value={workflow} onChange={e=>setWorkflow(e.target.value)}>{(caps.data?.workflows??[]).map(x=><MenuItem key={x} value={x}>{pretty(x)}</MenuItem>)}</Select></FormControl>
   <FormControl fullWidth><InputLabel>Execution mode</InputLabel><Select label="Execution mode" value={mode} onChange={e=>setMode(e.target.value)}>{["live","batch","replay","historical"].map(x=><MenuItem key={x} value={x}>{pretty(x)}</MenuItem>)}</Select></FormControl>
   <FormControl fullWidth><InputLabel>Window size</InputLabel><Select label="Window size" value={windowSize} onChange={e=>setWindowSize(Number(e.target.value))}>{[4,8,12,16,24,32].map(x=><MenuItem key={x} value={x}>{x} time steps</MenuItem>)}</Select></FormControl>
   {kind==="bigru"&&mode==="live"&&<Alert severity="warning">BiGRU is non-causal. Select replay, batch or historical mode.</Alert>}
   {preview.data&&<Box sx={{p:1.5,bgcolor:"grey.50",borderRadius:2}}><Typography variant="body2"><b>{preview.data.total_rows.toLocaleString()}</b> rows available</Typography><Typography variant="body2"><b>{numericColumns.length}</b> numeric features recognised</Typography><Typography variant="caption" color="text.secondary">{numericColumns.slice(0,8).join(", ")}{numericColumns.length>8?"…":""}</Typography></Box>}
   <Button variant="contained" startIcon={<Play size={18}/>} onClick={()=>run.mutate()} disabled={run.isPending||!selectedId||matrix.length<windowSize||(kind==="bigru"&&mode==="live")}>{run.isPending?"Running inference…":"Run edge inference"}</Button>
   {matrix.length>0&&matrix.length<windowSize&&<Alert severity="warning">The dataset does not contain enough complete numeric rows for the selected window.</Alert>}{run.isError&&<Alert severity="error">{run.error instanceof Error?run.error.message:"Inference failed."}</Alert>}
  </Stack></CardContent></Card></Grid>
  <Grid item xs={12} lg={7}><Stack spacing={2}><Card variant="outlined"><CardContent><Stack direction="row" gap={1} alignItems="center"><Cpu size={20}/><Typography variant="h6">Runtime readiness</Typography></Stack><Stack direction="row" gap={1} flexWrap="wrap" mt={2}><Chip color={caps.data?.edge_ready?"success":"error"} label={caps.data?.edge_ready?"Edge ready":"Unavailable"}/>{(caps.data?.architectures??[]).map(x=><Chip key={x} label={x}/>)}</Stack><Typography mt={2}><b>Accelerators:</b> {(caps.data?.accelerators??[]).join(", ")||"CPU"}</Typography><Typography><b>Connectors:</b> {(caps.data?.connectors??[]).join(", ")||"Local runtime"}</Typography></CardContent></Card>
   {result?<Card variant="outlined"><CardContent><Stack direction="row" gap={1} alignItems="center"><Activity size={20}/><Typography variant="h6">Inference result</Typography></Stack><Grid container spacing={1.5} mt={.5}>{objectMetrics.map(([k,v])=><Grid item xs={12} sm={6} key={k}><Metric label={k} value={v}/></Grid>)}</Grid>{objectMetrics.length===0&&<Alert severity="success" sx={{mt:2}}>Inference completed successfully. The result has been stored by the backend runtime.</Alert>}</CardContent></Card>:<Alert severity="info">Choose an uploaded dataset and run inference to display the prediction.</Alert>}
  </Stack></Grid></Grid>
 </Stack>;
}
