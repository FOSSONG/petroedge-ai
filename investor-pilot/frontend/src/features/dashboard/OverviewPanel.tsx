import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { Activity, CheckCircle2, CircleDashed, Database, RefreshCw, Server, Workflow } from "lucide-react";
import { fetchSprint2Operations, type OperationsResponse } from "../platform/platformApi";
import { useRealtime } from "../../realtime";

const label=(v:string)=>v.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const EMPTY: OperationsResponse={generated_at:"",summary:{datasets:0,active_wells:0,running_jobs:0,registered_models:0,failed_jobs:0,realtime_clients:0},current_dataset:null,processing_queue:[],services:[],workflow:[]};

export function OverviewPanel(){
 const realtime=useRealtime();
 const query=useQuery({queryKey:["sprint2","operations"],queryFn:fetchSprint2Operations,refetchInterval:30000,retry:2});
 useEffect(()=>{if(realtime.events.length) void query.refetch();},[realtime.events.length]);
 const data=query.data??EMPTY;
 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4}}}>
   <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2} alignItems={{md:"center"}} sx={{position:"relative",zIndex:1}}>
    <Box><Typography variant="overline">Intelligent Operations Centre</Typography><Typography variant="h4" fontWeight={900}>Live PetroEdge orchestration</Typography><Typography mt={.5}>Backend-connected datasets, AI jobs, workflows, services and real-time events.</Typography></Box>
    <Stack direction="row" spacing={1}><Chip label={realtime.connected?"Realtime connected":"Realtime offline"} color={realtime.connected?"success":"warning"}/><Button variant="contained" color="inherit" startIcon={<RefreshCw size={17}/>} onClick={()=>void query.refetch()}>Refresh</Button></Stack>
   </Stack>
  </Paper>
  {query.isFetching&&<LinearProgress/>}
  {query.isError&&<Alert severity="warning" action={<Button size="small" onClick={()=>void query.refetch()}>Retry</Button>}>Live operations data is temporarily unavailable. Safe defaults are shown, so the page remains usable.</Alert>}
  <Grid container spacing={2}>{Object.entries(data.summary??EMPTY.summary).map(([k,v])=><Grid item xs={6} md={2} key={k}><Paper variant="outlined" sx={{p:2.2,height:"100%"}}><Typography variant="caption" color="text.secondary">{label(k)}</Typography><Typography variant="h4" fontWeight={800} mt={.5}>{Number(v??0).toLocaleString()}</Typography></Paper></Grid>)}</Grid>
  <Grid container spacing={3}>
   <Grid item xs={12} lg={7}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Stack direction="row" gap={1} alignItems="center" mb={2}><Workflow/><Typography variant="h6">Processing workflow</Typography></Stack>{(data.workflow??[]).length===0?<Typography color="text.secondary">Upload a dataset to initialise the workflow.</Typography>:<Stack spacing={1.2}>{(data.workflow??[]).map((stage,index)=><Box key={`${stage.name}-${index}`} sx={{p:1.5,borderRadius:2,bgcolor:"action.hover"}}><Stack direction="row" alignItems="center" gap={1.2}>{stage.status==="completed"?<CheckCircle2 size={19}/>:<CircleDashed size={19}/>}<Box flex={1}><Typography fontWeight={700}>{stage.order??index+1}. {stage.name??"Workflow stage"}</Typography><Typography variant="caption" color="text.secondary">{stage.message??"No status detail"}</Typography></Box><Chip size="small" label={stage.status??"pending"} color={stage.status==="completed"?"success":"default"}/></Stack></Box>)}</Stack>}</Paper></Grid>
   <Grid item xs={12} lg={5}><Stack spacing={3}><Paper variant="outlined" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center" mb={2}><Database/><Typography variant="h6">Current dataset</Typography></Stack>{data.current_dataset?<><Typography fontWeight={800}>{data.current_dataset.name??"Unnamed dataset"}</Typography><Typography variant="body2" color="text.secondary">{data.current_dataset.file_name??"File unavailable"}</Typography><Stack direction="row" gap={1} mt={1.5} flexWrap="wrap"><Chip size="small" label={`${data.current_dataset.row_count??0} rows`}/><Chip size="small" label={`${data.current_dataset.column_count??0} curves`}/><Chip size="small" color="success" label={data.current_dataset.status??"unknown"}/></Stack></>:<Typography color="text.secondary">No dataset registered.</Typography>}</Paper>
   <Paper variant="outlined" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center" mb={2}><Server/><Typography variant="h6">Backend services</Typography></Stack>{(data.services??[]).length===0?<Typography color="text.secondary">Service telemetry is unavailable.</Typography>:<Stack spacing={1.2}>{(data.services??[]).map((s,index)=><Stack direction="row" key={`${s.name}-${index}`} justifyContent="space-between" gap={2}><Box><Typography fontWeight={700}>{s.name??"Service"}</Typography><Typography variant="caption" color="text.secondary">{s.detail??"No detail"}</Typography></Box><Chip size="small" label={s.status??"unknown"} color={s.status==="online"?"success":s.status==="offline"?"error":"default"}/></Stack>)}</Stack>}</Paper></Stack></Grid>
  </Grid>
  <Paper variant="outlined" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center" mb={2}><Activity/><Typography variant="h6">Processing queue</Typography></Stack>{(data.processing_queue??[]).length===0?<Typography color="text.secondary">No queued or running AI jobs.</Typography>:<Stack spacing={2}>{(data.processing_queue??[]).map((job,index)=><Box key={job.id??index}><Stack direction="row" justifyContent="space-between"><Box><Typography fontWeight={700}>{job.name??"AI job"}</Typography><Typography variant="caption" color="text.secondary">{label(job.task??"task")} · {job.stage||job.status||"queued"}</Typography></Box><Typography fontWeight={700}>{Number(job.progress??0)}%</Typography></Stack><LinearProgress variant="determinate" value={Math.max(0,Math.min(100,Number(job.progress??0)))} sx={{mt:1}}/></Box>)}</Stack>}</Paper>
 </Stack>;
}
