import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Chip, CircularProgress, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { BarChart3 } from "lucide-react";
import { SafePlot } from "../../components/SafePlot";
import { fetchExperiments, type ExperimentSummary } from "./platformApi";

const numericEntries=(metrics:unknown):Array<[string,number]>=>{
 if(!metrics||typeof metrics!=="object"||Array.isArray(metrics))return [];
 return Object.entries(metrics as Record<string,unknown>).flatMap(([k,v])=>typeof v==="number"&&Number.isFinite(v)?[[k,v] as [string,number]]:[]);
};
const safeMetrics=(experiment?:ExperimentSummary)=>numericEntries(experiment?.metrics);

export function ModelEvaluationPanel(){
 const q=useQuery({queryKey:["platform","experiments"],queryFn:fetchExperiments,refetchInterval:15000});
 const completed=useMemo(()=>(Array.isArray(q.data)?q.data:[]).filter(e=>e&&e.status==="completed"),[q.data]);
 const [chosen,setChosen]=useState(""); const selected=completed.find(e=>e.experiment_id===(chosen||completed[0]?.experiment_id)); const metrics=safeMetrics(selected);
 const names=metrics.map(([k])=>k.replace(/_/g," ")); const values=metrics.map(([,v])=>v);
 return <Stack spacing={3}>
  <Paper className="hero-panel" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center"><BarChart3/><Box><Typography variant="h4" fontWeight={900}>Model Evaluation</Typography><Typography>Defensive evaluation workspace for completed model and AI-agent experiments.</Typography></Box></Stack></Paper>
  {q.isLoading&&<Stack alignItems="center" py={6}><CircularProgress/></Stack>}
  {q.isError&&<Alert severity="error">Evaluation data could not be loaded.</Alert>}
  {!q.isLoading&&completed.length===0&&<Alert severity="info">No completed experiment with evaluation results is available yet. Run an experiment or agent workflow, then return here.</Alert>}
  {completed.length>0&&<><FormControl fullWidth><InputLabel>Completed experiment</InputLabel><Select value={selected?.experiment_id??""} label="Completed experiment" onChange={e=>setChosen(e.target.value)}>{completed.map(e=><MenuItem key={e.experiment_id} value={e.experiment_id}>{e.name} · {e.algorithm}</MenuItem>)}</Select></FormControl>
  <Stack direction="row" gap={1} flexWrap="wrap"><Chip label={selected?.task??"Unknown task"}/><Chip label={selected?.validation_strategy||"Validation strategy not recorded"}/><Chip color="success" label={`${metrics.length} numeric metrics`}/></Stack>
  {metrics.length===0?<Alert severity="warning">This completed experiment returned no valid numeric metrics. The page remains stable rather than rendering a blank screen.</Alert>:<>
   <Box display="grid" gridTemplateColumns={{xs:"1fr",sm:"repeat(2,1fr)",lg:"repeat(4,1fr)"}} gap={2}>{metrics.slice(0,12).map(([k,v])=><Paper key={k} variant="outlined" sx={{p:2.5}}><Typography color="text.secondary">{k.replace(/_/g," ")}</Typography><Typography variant="h4" fontWeight={850}>{Math.abs(v)<=1?v.toFixed(3):v.toFixed(2)}</Typography></Paper>)}</Box>
   <Paper variant="outlined" sx={{p:2}}><SafePlot data={[{type:"bar",x:names,y:values,hovertemplate:"%{x}: %{y:.4f}<extra></extra>"}]} layout={{autosize:true,height:420,margin:{l:65,r:25,t:35,b:120},xaxis:{tickangle:-35},yaxis:{title:"Metric value"},paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)"}} config={{responsive:true,displaylogo:false,scrollZoom:true}}/></Paper>
   <Paper variant="outlined"><Table size="small"><TableHead><TableRow><TableCell>Metric</TableCell><TableCell align="right">Value</TableCell></TableRow></TableHead><TableBody>{metrics.map(([k,v])=><TableRow key={k}><TableCell>{k.replace(/_/g," ")}</TableCell><TableCell align="right">{v.toFixed(6)}</TableCell></TableRow>)}</TableBody></Table></Paper>
  </>}</>}</Stack>;
}
