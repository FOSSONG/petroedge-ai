import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Alert,Button,MenuItem,Stack,TextField,Typography} from "@mui/material";
import {apiRequest} from "../../api/http";
import {fetchDatasets} from "./platformApi";
import {SafePlot} from "../../components/SafePlot";
type Row=Record<string,number|null>;
const curves=[["gamma_ray_api","GR (API)"],["resistivity_ohmm","RT (ohm.m)"],["density_gcc","RHOB (g/cm3)"],["neutron_porosity_vv","NPHI (v/v)"],["sonic_usft","DT (us/ft)"],["caliper_in","Caliper (in)"]];
export function WellLogPlotlyPanel(){
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [chosen,setChosen]=useState(""); const [version,setVersion]=useState(0);
 const id=chosen||datasets.data?.[0]?.dataset_id||"";
 const logs=useQuery({queryKey:["measured-logs",id],queryFn:()=>apiRequest<{rows:Row[];qc:string}>(`/datasets/${id}/crossplot-data`),enabled:!!id});
 const rows=logs.data?.rows??[];
 const available=curves.filter(([key])=>rows.some(r=>r.depth_m!=null&&r[key]!=null));
 const layout:Record<string,unknown>={height:760,showlegend:false,margin:{l:65,r:20,t:80,b:30},yaxis:{autorange:"reversed",title:{text:"Measured depth (m)"}},uirevision:version};
 const traces=available.map(([key,label],i)=>{
  const axis=i?`x${i+1}`:"x";
  layout[i?`xaxis${i+1}`:"xaxis"]={domain:[i/available.length,(i+.9)/available.length],title:{text:label},side:"top",type:key==="resistivity_ohmm"?"log":"linear"};
  return {x:rows.map(r=>r[key]),y:rows.map(r=>r.depth_m),type:"scattergl",mode:"lines",connectgaps:false,name:label,xaxis:axis,yaxis:"y"};
 });
 return <Stack spacing={2}><Typography variant="h4">Interactive measured logs</Typography><Typography>Each measured curve uses its own valid samples. Missing values remain gaps. Reservoir interpretations are available in Reservoir Intelligence.</Typography><TextField select label="Dataset" value={id} onChange={e=>setChosen(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</TextField><Button disabled={logs.isFetching||datasets.isFetching} onClick={()=>{void datasets.refetch();void logs.refetch();setVersion(v=>v+1)}}>Refresh</Button>{(logs.isError||datasets.isError)&&<Alert severity="error">{logs.error?.message||datasets.error?.message}</Alert>}{logs.isFetching&&<Typography>Loading measured logs...</Typography>}{logs.data&&<><Alert severity="info">{logs.data.qc} {rows.length.toLocaleString()} source rows.</Alert>{available.length?<SafePlot key={`${id}-${version}`} data={traces} layout={layout} minHeight={760}/>:<Alert severity="warning">No valid depth-linked curves. In LAS Wizard, select numeric measured depth, not Well_id, and check units.</Alert>}</>}</Stack>;
}
