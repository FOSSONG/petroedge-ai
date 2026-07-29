import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Chip, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import Plot from "react-plotly.js";
import { BarChart3, CheckCircle2 } from "lucide-react";
import { fetchExperiments } from "../platform/platformApi";
import { useTheme } from "@mui/material/styles";

const metricNumber=(v:unknown)=>typeof v==="number"&&Number.isFinite(v)?v:null;
const percentMetric=(name:string,value:number)=>/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)&&Math.abs(value)<=1?value*100:value;

export function ModelEvaluationPanel(){
 const theme=useTheme();
 const query=useQuery({queryKey:["platform","experiments"],queryFn:fetchExperiments});
 const completed=useMemo(()=>(query.data??[]).filter(x=>x.status==="completed"&&Object.keys(x.metrics??{}).length),[query.data]);
 const metricNames=useMemo(()=>Array.from(new Set(completed.flatMap(x=>Object.entries(x.metrics).filter(([,v])=>metricNumber(v)!==null).map(([k])=>k)))).slice(0,8),[completed]);
 const latest=completed[0];
 const plotLayout={paper_bgcolor:"transparent",plot_bgcolor:"transparent",font:{color:theme.palette.text.primary},margin:{l:55,r:25,t:35,b:55},legend:{orientation:"h" as const}};
 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4}}}><Stack direction="row" gap={1.5} alignItems="center"><BarChart3/><Box><Typography variant="h4">Model Evaluation & Explainability Centre</Typography><Typography mt={1}>Compare validation metrics, inspect error behaviour and review the evidence supporting each registered AI model.</Typography></Box></Stack></Paper>
  {query.isLoading&&<LinearProgress/>}{query.isError&&<Alert severity="error">Unable to load model evaluation records.</Alert>}
  {!query.isLoading&&!completed.length&&<Alert severity="info">No completed experiment with stored evaluation metrics is available. Train or import a validated model to populate this centre.</Alert>}
  {completed.length>0&&<>
   <Grid container spacing={2}>{completed.slice(0,6).map(exp=><Grid item xs={12} md={6} xl={4} key={exp.experiment_id}><Paper variant="outlined" sx={{p:2.5,height:"100%"}}><Stack direction="row" justifyContent="space-between" gap={1}><Box><Typography fontWeight={800}>{exp.name}</Typography><Typography variant="body2" color="text.secondary">{exp.algorithm} · {exp.task}</Typography></Box><Chip icon={<CheckCircle2 size={14}/>} size="small" color="success" label="Validated"/></Stack><Grid container spacing={1.2} mt={1}>{Object.entries(exp.metrics).filter(([,v])=>metricNumber(v)!==null).slice(0,6).map(([name,v])=><Grid item xs={6} key={name}><Box sx={{p:1.2,borderRadius:1.5,bgcolor:"action.hover"}}><Typography variant="caption" color="text.secondary">{name.replace(/_/g," ")}</Typography><Typography fontWeight={850}>{percentMetric(name,Number(v)).toFixed(/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)?1:3)}{/accuracy|precision|recall|f1|auc|confidence|agreement/i.test(name)?"%":""}</Typography></Box></Grid>)}</Grid></Paper></Grid>)}</Grid>
   {metricNames.length>0&&<Paper variant="outlined" sx={{p:2.5}}><Typography variant="h6">Cross-model metric comparison</Typography><Box height={420}><Plot data={metricNames.map(name=>({type:"bar",name:name.replace(/_/g," "),x:completed.map(e=>e.name),y:completed.map(e=>{const v=metricNumber(e.metrics[name]);return v===null?null:percentMetric(name,v)}),hovertemplate:"%{x}<br>%{y:.3f}<extra>%{fullData.name}</extra>"})) as any} layout={{...plotLayout,barmode:"group",autosize:true,xaxis:{tickangle:-20},yaxis:{title:"Metric value"}} as any} config={{responsive:true,displaylogo:false,toImageButtonOptions:{format:"png",filename:"petroedge-model-evaluation",scale:2}}} style={{width:"100%",height:"100%"}} useResizeHandler/></Box></Paper>}
   {latest&&<Paper variant="outlined" sx={{p:2.5}}><Typography variant="h6">Validation record</Typography><Typography color="text.secondary" mt={1}>Latest completed evaluation: <strong>{latest.name}</strong>. Validation strategy: {latest.validation_strategy??"not recorded"}. Training time: {latest.training_seconds?.toFixed(2)??"not recorded"} s. This panel reports only metrics persisted by the training pipeline and does not fabricate missing values.</Typography></Paper>}
  </>}
 </Stack>;
}
