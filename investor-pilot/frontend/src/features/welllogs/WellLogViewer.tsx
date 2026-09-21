import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Accordion, AccordionSummary, AccordionDetails, Alert, Box, Button, FormControl, InputLabel, MenuItem, Paper, Select, Stack, TextField, Typography } from "@mui/material";
import { SafePlot } from "../../components/SafePlot";
import { apiRequest } from "../../api/http";
import { fetchDatasets } from "../platform/platformApi";
import { SavedAnalysesPanel } from "../wells/SavedAnalysesPanel";
import { WellExplorerPanel } from "../wells/WellExplorerPanel";

type Row=Record<string,number|null>;
type PlotData={source_rows:number;rows:Row[];qc:string};
const value=(v:unknown):number|null=>typeof v==="number"&&Number.isFinite(v)?v:null;
const definitions=[
 {title:"RHOB vs NPHI",x:"neutron_porosity_vv",y:"density_gcc",xlabel:"NPHI (v/v)",ylabel:"RHOB (g/cm3)",log:false},
 {title:"Pickett plot",x:"density_porosity",y:"resistivity_ohmm",xlabel:"Density porosity (v/v, estimated)",ylabel:"RT (ohm.m)",log:true},
 {title:"GR vs RHOB",x:"gamma_ray_api",y:"density_gcc",xlabel:"GR (API)",ylabel:"RHOB (g/cm3)",log:false},
 {title:"GR vs NPHI",x:"gamma_ray_api",y:"neutron_porosity_vv",xlabel:"GR (API)",ylabel:"NPHI (v/v)",log:false},
 {title:"GR vs RT",x:"gamma_ray_api",y:"resistivity_ohmm",xlabel:"GR (API)",ylabel:"RT (ohm.m)",log:false,logY:true},
];
export function WellLogViewer(){
 const client=useQueryClient();
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [chosen,setChosen]=useState("");const datasetId=chosen||datasets.data?.[0]?.dataset_id||"";
 const data=useQuery({queryKey:["welllogs","crossplots",datasetId],queryFn:()=>apiRequest<PlotData>(`/datasets/${datasetId}/crossplot-data`),enabled:Boolean(datasetId)});
 const [top,setTop]=useState("");const [base,setBase]=useState("");const [version,setVersion]=useState(0);
 const [rw,setRw]=useState(.1);const [matrix,setMatrix]=useState(2.65);const [fluid,setFluid]=useState(1);
 const [refreshing,setRefreshing]=useState(false);const [notice,setNotice]=useState("");const [error,setError]=useState("");
 const selected=useMemo(()=> (data.data?.rows??[]).filter(row=>{
   if(top===""&&base==="")return true;const depth=value(row.depth_m);
   return depth!==null&&(top===""||depth>=Number(top))&&(base===""||depth<=Number(base));
 }).map((row):Row=>({...row,density_porosity:value(row.density_gcc)!==null&&matrix>fluid?(matrix-row.density_gcc!)/(matrix-fluid):null})),[data.data,top,base,matrix,fluid]);
 const refresh=async()=>{setRefreshing(true);setError("");setNotice("");try{await client.refetchQueries({type:"active"},{throwOnError:true});setVersion(v=>v+1);setNotice("Feature refreshed: datasets, measurements and plots reloaded.");}catch(e){setError(e instanceof Error?e.message:"Refresh failed");}finally{setRefreshing(false);}};
 const charts=useMemo(()=>(<Box display="grid" gridTemplateColumns={{xs:"1fr",xl:"repeat(2,1fr)"}} gap={2}>{definitions.map(def=>{
   const valid=selected.filter(r=>value(r[def.x])!==null&&value(r[def.y])!==null&&(!def.log||(r[def.x]!>0&&r[def.x]!<=.6))&&(!(def.log||def.logY)||r[def.y]!>0));
   const stride=Math.max(1,Math.ceil(valid.length/5000));const points=valid.filter((_,i)=>i%stride===0);
   const traces:any[]=[{type:"scatter",mode:"markers",name:"Measured pairs",x:points.map(r=>r[def.x]),y:points.map(r=>r[def.y]),customdata:points.map(r=>r.depth_m),marker:{size:5,opacity:.65},hovertemplate:`${def.xlabel}: %{x:.3f}<br>${def.ylabel}: %{y:.3f}<br>MD: %{customdata} m<extra></extra>`}];
   if(def.log&&rw>0&&matrix>fluid){const phis=[.01,.02,.04,.08,.16,.32,.6];for(const sw of [1,.5,.25])traces.push({type:"scatter",mode:"lines",name:`Sw ${sw*100}% scenario`,x:phis,y:phis.map(phi=>rw/(phi*phi*sw*sw)),line:{dash:"dot"}});}
   return <Paper key={def.title} variant="outlined" sx={{p:2,minWidth:0}}><Typography variant="h6">{def.title}</Typography><Typography variant="caption">{valid.length.toLocaleString()} valid pairs; {points.length.toLocaleString()} displayed</Typography>{points.length?<SafePlot key={`${datasetId}-${def.title}-${version}`} data={traces} minHeight={420} layout={{height:420,autosize:true,margin:{l:75,r:25,t:25,b:80},xaxis:{title:{text:def.xlabel},type:def.log?"log":"linear",automargin:true},yaxis:{title:{text:def.ylabel},type:def.log||def.logY?"log":"linear",automargin:true},legend:{orientation:"h",y:-.25},paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)"}} config={{responsive:true,displaylogo:false,scrollZoom:true}}/>:<Alert severity="info">No valid pairs for this plot. Review available curves, units and the selected depth interval in LAS Wizard.</Alert>}</Paper>;
  })}</Box>),[selected,rw,matrix,fluid,datasetId,version]);
 return <Stack spacing={3}>
  <Paper className="hero-panel" sx={{p:3}}><Stack direction="row" justifyContent="space-between"><Box><Typography variant="h4">Well Log Analysis</Typography><Typography>Five interactive interpretation crossplots using the full available depth range.</Typography></Box><Button variant="contained" onClick={refresh} disabled={refreshing}>{refreshing?"Refreshing...":"Refresh"}</Button></Stack></Paper>
  {notice&&<Alert severity="success">{notice}</Alert>}{error&&<Alert severity="error">{error}</Alert>}
  <FormControl fullWidth><InputLabel>Dataset</InputLabel><Select label="Dataset" value={datasetId} onChange={e=>{setChosen(e.target.value);setTop("");setBase("");setNotice("");}}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl>
  {(datasets.isFetching||data.isFetching)&&<Alert severity="info">Loading full-depth measurements...</Alert>}
  {(datasets.isError||data.isError)&&<Alert severity="error">{datasets.error?.message||data.error?.message}</Alert>}
  {!datasetId&&!datasets.isLoading&&<Alert severity="info">Upload a well-log dataset to begin.</Alert>}
  <Stack direction={{xs:"column",md:"row"}} spacing={2}><TextField label="Top measured depth (m)" type="number" value={top} onChange={e=>setTop(e.target.value)}/><TextField label="Base measured depth (m)" type="number" value={base} onChange={e=>setBase(e.target.value)}/><Button onClick={()=>{setTop("");setBase("");setVersion(v=>v+1);}}>Entire dataset</Button></Stack>
  {top!==""&&base!==""&&Number(top)>Number(base)&&<Alert severity="warning">Top depth must be less than or equal to base depth.</Alert>}
  {data.data&&<Alert severity="info">{data.data.source_rows.toLocaleString()} source rows inspected; {selected.length.toLocaleString()} in the selected interval. {data.data.qc} Each plot displays up to 5,000 evenly spaced valid pairs across this interval.</Alert>}
  <Paper variant="outlined" sx={{p:2}}><Stack spacing={2}><Typography>Pickett assumptions: density-derived porosity, Archie a=1, m=2 and n=2. Reference lines are scenarios, not fluid confirmation. Shale and gas effects can invalidate these assumptions.</Typography><Stack direction={{xs:"column",md:"row"}} spacing={2}><TextField label="Rw (ohm.m)" type="number" value={rw} onChange={e=>setRw(Number(e.target.value))}/><TextField label="Matrix density (g/cm3)" type="number" value={matrix} onChange={e=>setMatrix(Number(e.target.value))}/><TextField label="Fluid density (g/cm3)" type="number" value={fluid} onChange={e=>setFluid(Number(e.target.value))}/></Stack>{(!(rw>0)||!(matrix>fluid))&&<Alert severity="warning">Rw must be positive and matrix density must exceed fluid density.</Alert>}</Stack></Paper>
  {charts}
  <Accordion TransitionProps={{unmountOnExit:true}}><AccordionSummary>Saved analyses and provenance</AccordionSummary><AccordionDetails><SavedAnalysesPanel/></AccordionDetails></Accordion>
  <Accordion TransitionProps={{unmountOnExit:true}}><AccordionSummary>Mapped well logs and analysis inputs</AccordionSummary><AccordionDetails><WellExplorerPanel/></AccordionDetails></Accordion>
 </Stack>;
}
