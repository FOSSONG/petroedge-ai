import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { SafePlot } from "../../components/SafePlot";
import { BarChart3, CheckCircle2, RefreshCw } from "lucide-react";
import { fetchExperiments, type ExperimentSummary } from "../platform/platformApi";
import { useTheme } from "@mui/material/styles";
import { refreshPlatform } from "../../lib/refresh";

const metricNumber=(v:unknown)=>typeof v==="number"&&Number.isFinite(v)?v:null;
const percentMetric=(name:string,value:number)=>/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)&&Math.abs(value)<=1?value*100:value;
const metricsOf=(experiment:Partial<ExperimentSummary>)=>experiment.metrics&&typeof experiment.metrics==="object"&&!Array.isArray(experiment.metrics)?experiment.metrics:{};

function normaliseExperiments(value:unknown):ExperimentSummary[]{
 if(Array.isArray(value))return value.filter((item):item is ExperimentSummary=>Boolean(item&&typeof item==="object"));
 if(value&&typeof value==="object"){
  const record=value as Record<string,unknown>;
  for(const key of ["experiments","items","results","data"]){if(Array.isArray(record[key]))return record[key] as ExperimentSummary[];}
 }
 return [];
}

export function ModelEvaluationPanel(){
 const theme=useTheme();
 const qc=useQueryClient();
 const query=useQuery({queryKey:["platform","experiments"],queryFn:fetchExperiments,retry:1});
 const experiments=useMemo(()=>normaliseExperiments(query.data),[query.data]);
 const completed=useMemo(()=>experiments.filter(x=>String(x.status??"").toLowerCase()==="completed"&&Object.keys(metricsOf(x)).length>0),[experiments]);
 const metricNames=useMemo(()=>Array.from(new Set(completed.flatMap(x=>Object.entries(metricsOf(x)).filter(([,v])=>metricNumber(v)!==null).map(([k])=>k)))).slice(0,8),[completed]);
 const latest=completed[0];
 const plotLayout=useMemo(()=>({paper_bgcolor:"transparent",plot_bgcolor:"transparent",font:{color:theme.palette.text.primary},margin:{l:65,r:25,t:35,b:75},legend:{orientation:"h" as const},xaxis:{tickangle:-20,automargin:true},yaxis:{title:"Metric value",automargin:true}}),[theme.palette.text.primary]);
 const plotData=useMemo(()=>metricNames.map(name=>({type:"bar",name:name.replace(/_/g," "),x:completed.map(e=>String(e.name??e.experiment_id??"Unnamed model")),y:completed.map(e=>{const v=metricNumber(metricsOf(e)[name]);return v===null?null:percentMetric(name,v)}),hovertemplate:"%{x}<br>%{y:.3f}<extra>%{fullData.name}</extra>"})),[metricNames,completed]);

 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4},bgcolor:"background.paper",color:"text.primary",border:1,borderColor:"divider"}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2} alignItems={{md:"center"}}><Stack direction="row" gap={1.5} alignItems="center"><BarChart3/><Box><Typography variant="h4">Model Evaluation & Explainability Centre</Typography><Typography mt={1} color="text.secondary">Compare validation metrics, inspect error behaviour and review the evidence supporting each registered AI model.</Typography></Box></Stack><Button variant="contained" startIcon={<RefreshCw size={17}/>} onClick={()=>void refreshPlatform(qc,[["platform","experiments"],["models"]])}>Refresh</Button></Stack></Paper>
  {query.isLoading&&<LinearProgress/>}
  {query.isError&&<Alert severity="error" action={<Button color="inherit" size="small" onClick={()=>void query.refetch()}>Retry</Button>}>Unable to load model evaluation records: {query.error instanceof Error?query.error.message:"Unknown API error"}</Alert>}
  {!query.isLoading&&!query.isError&&!completed.length&&<Alert severity="info">No completed experiment with stored evaluation metrics is available. Train or import a validated model to populate this centre.</Alert>}
  {completed.length>0&&<>
   <Grid container spacing={2}>{completed.slice(0,6).map((exp,index)=><Grid item xs={12} md={6} xl={4} key={String(exp.experiment_id??index)}><Paper variant="outlined" sx={{p:2.5,height:"100%"}}><Stack direction="row" justifyContent="space-between" gap={1}><Box><Typography fontWeight={800}>{String(exp.name??"Unnamed experiment")}</Typography><Typography variant="body2" color="text.secondary">{String(exp.algorithm??"Algorithm not recorded")} · {String(exp.task??"Task not recorded")}</Typography></Box><Chip icon={<CheckCircle2 size={14}/>} size="small" color="success" label="Validated"/></Stack><Grid container spacing={1.2} mt={1}>{Object.entries(metricsOf(exp)).filter(([,v])=>metricNumber(v)!==null).slice(0,6).map(([name,v])=><Grid item xs={6} key={name}><Box sx={{p:1.2,borderRadius:1.5,bgcolor:"action.hover"}}><Typography variant="caption" color="text.secondary">{name.replace(/_/g," ")}</Typography><Typography fontWeight={850}>{percentMetric(name,Number(v)).toFixed(/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)?1:3)}{/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)?"%":""}</Typography></Box></Grid>)}</Grid></Paper></Grid>)}</Grid>
   {metricNames.length>0&&<Paper variant="outlined" sx={{p:2.5}}><Typography variant="h6">Cross-model metric comparison</Typography><Box height={420} mt={1}><SafePlot data={plotData} layout={{...plotLayout,barmode:"group",autosize:true}} config={{responsive:true,displaylogo:false,toImageButtonOptions:{format:"png",filename:"petroedge-model-evaluation",scale:2}}} style={{width:"100%",height:"100%"}} useResizeHandler/></Box></Paper>}
   {latest&&<Paper variant="outlined" sx={{p:2.5}}><Typography variant="h6">Validation record</Typography><Typography color="text.secondary" mt={1}>Latest completed evaluation: <strong>{String(latest.name??"Unnamed experiment")}</strong>. Validation strategy: {String(latest.validation_strategy??"not recorded")}. Training time: {typeof latest.training_seconds==="number"?latest.training_seconds.toFixed(2):"not recorded"} s. This panel reports only metrics persisted by the training pipeline and does not fabricate missing values.</Typography></Paper>}
  </>}
 </Stack>;
}
