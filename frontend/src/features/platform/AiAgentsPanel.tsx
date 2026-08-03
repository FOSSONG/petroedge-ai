import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, CircularProgress, FormControl, InputLabel, MenuItem, Paper, Select, Stack, TextField, Typography } from "@mui/material";
import { Bot, Play, Users } from "lucide-react";
import { apiRequest } from "../../api/http";
import { fetchDatasets } from "./platformApi";

type Agent = { key:string; name:string; domain:string; status:string };
type AgentResult = { agent_key:string; agent_name:string; status:string; confidence:number; findings:string[]; recommendation:string; evidence:string[] };
type PanelResult = { status:string; consensus:string; confidence:number; agreement_percent:number; recommendations:string[]; agents:AgentResult[] };

const fetchAgents=()=>apiRequest<Agent[]>("/agents");
const runAgent=(key:string,payload:Record<string,unknown>)=>apiRequest<AgentResult>(`/agents/${key}/run`,{method:"POST",body:JSON.stringify(payload)});
const runPanel=(payload:Record<string,unknown>)=>apiRequest<PanelResult>("/agents/panel/run",{method:"POST",body:JSON.stringify(payload)});

export function AiAgentsPanel(){
 const agents=useQuery({queryKey:["agents"],queryFn:fetchAgents});
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [agentKey,setAgentKey]=useState(""); const [datasetId,setDatasetId]=useState(""); const [objective,setObjective]=useState("Evaluate lithology, fluid evidence and reservoir quality in the selected data.");
 const activeAgent=agentKey||agents.data?.[0]?.key||""; const activeDataset=datasetId||datasets.data?.[0]?.dataset_id||"";
 const single=useMutation({mutationFn:()=>runAgent(activeAgent,{dataset_id:activeDataset||null,objective})});
 const panel=useMutation({mutationFn:()=>runPanel({dataset_id:activeDataset||null,objective})});
 const result=panel.data; const cards=useMemo(()=>result?.agents??(single.data?[single.data]:[]),[result,single.data]);
 return <Stack spacing={3}>
  <Paper className="hero-panel" sx={{p:3}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Box><Stack direction="row" gap={1} alignItems="center"><Users/><Typography variant="h4" fontWeight={900}>AI Agents</Typography></Stack><Typography mt={1}>Run specialist petroleum-engineering agents individually or as a governed consensus panel.</Typography></Box><Chip label={`${agents.data?.length??0} agents registered`} sx={{alignSelf:"flex-start"}}/></Stack></Paper>
  {(agents.isError||datasets.isError)&&<Alert severity="error">Agent or dataset resources could not be loaded.</Alert>}
  <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Stack direction={{xs:"column",md:"row"}} gap={2}><FormControl fullWidth><InputLabel>Agent</InputLabel><Select value={activeAgent} label="Agent" onChange={e=>setAgentKey(e.target.value)}>{(agents.data??[]).map(a=><MenuItem key={a.key} value={a.key}>{a.name}</MenuItem>)}</Select></FormControl><FormControl fullWidth><InputLabel>Dataset</InputLabel><Select value={activeDataset} label="Dataset" onChange={e=>setDatasetId(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl></Stack><TextField multiline minRows={2} label="Analysis objective" value={objective} onChange={e=>setObjective(e.target.value)}/><Stack direction="row" gap={1}><Button variant="contained" startIcon={<Play/>} disabled={!activeAgent||single.isPending||panel.isPending} onClick={()=>single.mutate()}>Run selected agent</Button><Button variant="outlined" startIcon={<Bot/>} disabled={single.isPending||panel.isPending} onClick={()=>panel.mutate()}>Run consensus panel</Button></Stack></Stack></Paper>
  {(single.isPending||panel.isPending)&&<Stack alignItems="center" py={4}><CircularProgress/></Stack>}
  {(single.isError||panel.isError)&&<Alert severity="error">Agent execution failed. Confirm that the backend agents route is running.</Alert>}
  {result&&<Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Panel consensus</Typography><Typography mt={1}>{result.consensus}</Typography><Stack direction="row" gap={1} mt={2}><Chip color="success" label={`Confidence ${(result.confidence*100).toFixed(1)}%`}/><Chip label={`Agreement ${result.agreement_percent.toFixed(1)}%`}/></Stack>{result.recommendations.map(x=><Typography key={x} mt={1}>• {x}</Typography>)}</Paper>}
  <Box display="grid" gridTemplateColumns={{xs:"1fr",md:"repeat(2,1fr)"}} gap={2}>{cards.map(r=><Paper key={r.agent_key} variant="outlined" sx={{p:2.5}}><Stack direction="row" justifyContent="space-between"><Typography variant="h6">{r.agent_name}</Typography><Chip size="small" label={`${(r.confidence*100).toFixed(1)}%`}/></Stack>{r.findings.map(x=><Typography key={x} mt={1}>• {x}</Typography>)}<Typography mt={2} fontWeight={700}>Recommendation</Typography><Typography>{r.recommendation}</Typography></Paper>)}</Box>
 </Stack>;
}
