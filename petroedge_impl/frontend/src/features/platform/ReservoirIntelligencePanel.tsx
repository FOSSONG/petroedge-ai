import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, FormControl, Grid, InputLabel, LinearProgress, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import { Activity, Droplets, FileText, Layers3, RefreshCw } from "lucide-react";
import { SafePlot } from "../../components/SafePlot";
import { useTheme } from "@mui/material/styles";
import { downloadV1Report, fetchDatasets, fetchInterpretation } from "./platformApi";
import { refreshPlatform } from "../../lib/refresh";

const tracks=[
 {key:"gr",title:"Gamma ray",unit:"API",range:[0,150],log:false},
 {key:"rt",title:"Resistivity",unit:"ohm·m",range:[0.2,2000],log:true},
 {key:"rhob",title:"Density",unit:"g/cc",range:[1.95,2.95],log:false},
 {key:"nphi",title:"Neutron",unit:"v/v",range:[0.45,-0.15],log:false},
 {key:"dt",title:"Sonic",unit:"µs/ft",range:[40,180],log:false},
 {key:"porosity",title:"Porosity",unit:"v/v",range:[0,0.40],log:false},
 {key:"water_saturation",title:"Water saturation",unit:"v/v",range:[0,1],log:false},
 {key:"hydrocarbon_probability",title:"HC probability",unit:"%",range:[0,1],log:false},
];
const fluidOrder=["oil","gas","water","residual_hydrocarbon"];
const fluidCode:Record<string,number>={water:0,oil:1,gas:2,residual_hydrocarbon:3};
const labelFluid=(s:string)=>s.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const pct=(v:unknown)=>`${(Number(v??0)*100).toFixed(1)}%`;

export function ReservoirIntelligencePanel(){
 const theme=useTheme();const qc=useQueryClient();const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});const [datasetId,setDatasetId]=useState(()=>sessionStorage.getItem("petroedge_selected_dataset_id")??"");const selected=datasetId||(datasets.data?.[0]?.dataset_id??"");
 const interpretation=useQuery({queryKey:["reservoir","interpretation",selected],queryFn:()=>fetchInterpretation(selected),enabled:Boolean(selected)});
 const pdf=useMutation({mutationFn:()=>downloadV1Report(selected)});
 const rows=Array.isArray(interpretation.data?.samples)?interpretation.data.samples:[];
 const intervals=Array.isArray(interpretation.data?.intervals)?interpretation.data.intervals:[];
 const plotRows=useMemo(()=>{
  const maximumPoints=5000;
  if(rows.length<=maximumPoints)return rows;
  const stride=Math.ceil(rows.length/maximumPoints);
  return rows.filter((_row,index)=>index%stride===0||index===rows.length-1);
 },[rows]);
 const depthRange=useMemo(()=>{
  let minimum=Number.POSITIVE_INFINITY;
  let maximum=Number.NEGATIVE_INFINITY;
  for(const row of rows){
   const depth=Number(row.depth);
   if(Number.isFinite(depth)){minimum=Math.min(minimum,depth);maximum=Math.max(maximum,depth);}
  }
  return Number.isFinite(minimum)&&Number.isFinite(maximum)?[minimum,maximum]:[0,100];
 },[rows]);
 const summary=interpretation.data?.summary??{};const fluid=(summary.primary_fluid as string|undefined)??"uncertain";const probs=(summary.fluid_probabilities as Record<string,number>|undefined)??{};
 const evidence=(summary.fluid_evidence as Record<string,boolean>|undefined)??{};
 const layoutBase={paper_bgcolor:"transparent",plot_bgcolor:"transparent",font:{color:theme.palette.text.primary},margin:{l:68,r:18,t:40,b:48},hovermode:"closest" as const};
 return <Stack spacing={3}>
  <Paper className="hero-panel" sx={{p:{xs:3,md:4}}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Box><Chip label="Interactive petrophysical visualisation" className="hero-chip"/><Typography variant="h4" mt={1.5}>Reservoir Intelligence</Typography><Typography sx={{opacity:.9,mt:1}}>Pan, zoom, inspect and export calibrated multi-track log signatures with explicit water, oil and gas screening.</Typography></Box><Stack minWidth={{md:340}} gap={1.5}><FormControl sx={{bgcolor:"background.paper",borderRadius:1}}><InputLabel>Dataset</InputLabel><Select label="Dataset" value={selected} onChange={e=>{setDatasetId(e.target.value);sessionStorage.setItem("petroedge_selected_dataset_id",e.target.value)}}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl><Stack direction="row" gap={1}><Button variant="contained" color="inherit" startIcon={<RefreshCw size={17}/>} onClick={()=>void refreshPlatform(qc,[["platform","datasets"],["reservoir","interpretation",selected]])}>Refresh</Button><Button variant="contained" startIcon={<FileText size={17}/>} disabled={!selected||pdf.isPending} onClick={()=>pdf.mutate()} sx={{bgcolor:"background.paper",color:"primary.dark"}}>{pdf.isPending?"Preparing log PDF…":"Download log-signature PDF"}</Button></Stack></Stack></Stack></Paper>
  {datasets.isLoading&&<LinearProgress/>}{!datasets.isLoading&&!(datasets.data??[]).length&&<Alert severity="info">No dataset is available. Upload a well-log dataset in the Datasets tab to activate Reservoir Intelligence.</Alert>}{interpretation.isLoading&&<LinearProgress/>}{interpretation.isError&&<Alert severity="error">{interpretation.error instanceof Error?interpretation.error.message:"Interpretation failed."}</Alert>}{pdf.isError&&<Alert severity="error">PDF generation failed.</Alert>}
  {interpretation.data&&rows.length===0&&<Alert severity="info">The selected dataset contains no interpretable depth-indexed log records.</Alert>}{interpretation.data&&rows.length>0&&<>
   <Grid container spacing={2}><Grid item xs={12} md={5}><Paper variant="outlined" sx={{p:2.5,height:"100%"}}><Stack direction="row" gap={1} alignItems="center"><Droplets/><Typography variant="h6">Water, oil and gas interpretation</Typography></Stack><Typography variant="h4" mt={1}>{labelFluid(fluid)}</Typography><Typography color="text.secondary">Confidence {pct(summary.fluid_confidence)} · Basis: {String(summary.fluid_basis??"logged interval")}</Typography><Stack mt={2} gap={1}>{fluidOrder.map(name=><Box key={name}><Stack direction="row" justifyContent="space-between"><Typography>{labelFluid(name)}</Typography><Typography fontWeight={800}>{pct(probs[name])}</Typography></Stack><LinearProgress variant="determinate" value={Number(probs[name]??0)*100} sx={{height:9,borderRadius:4}}/></Box>)}</Stack><Stack direction="row" gap={1} flexWrap="wrap" mt={2}>{Object.entries(evidence).map(([name,available])=><Chip key={name} size="small" color={available?"success":"default"} variant={available?"filled":"outlined"} label={`${labelFluid(name)}: ${available?"available":"missing"}`}/>)}</Stack><Alert severity={summary.fluid_reliability==="low"?"warning":"info"} sx={{mt:2}}>Reliability: {String(summary.fluid_reliability??"unknown").toUpperCase()}. This is an evidence-weighted screening result. Confirm oil or gas with pressure gradients, formation tests, PVT, mud logs or production data.</Alert></Paper></Grid><Grid item xs={12} md={7}><Paper variant="outlined" sx={{p:2.5,height:"100%"}}><Stack direction="row" gap={1} alignItems="center"><Activity/><Typography variant="h6">Interpretation summary</Typography></Stack><Grid container spacing={1.5} mt={.5}>{[["Rows",summary.rows_interpreted],["Mean porosity",pct(summary.mean_porosity)],["Mean Sw",pct(summary.mean_water_saturation)],["Pay intervals",summary.pay_intervals],["Mean HC probability",pct(summary.mean_hydrocarbon_probability)],["Mapped curves",summary.mapped_curves]].map(([k,v])=><Grid item xs={6} md={4} key={String(k)}><Box sx={{p:1.5,bgcolor:"action.hover",borderRadius:1.5}}><Typography variant="caption" color="text.secondary">{String(k)}</Typography><Typography fontWeight={850}>{String(v??"—")}</Typography></Box></Grid>)}</Grid></Paper></Grid></Grid>

   <Grid container spacing={2}>
    <Grid item xs={12} lg={6}><Paper variant="outlined" sx={{p:1.5,height:470}}><Typography fontWeight={800}>Fluid probability by depth</Typography><SafePlot data={fluidOrder.map(name=>({type:"scatter",mode:"lines",x:plotRows.map(r=>Number((r.fluid_probabilities as Record<string,number>|undefined)?.[name]??0)*100),y:plotRows.map(r=>Number(r.depth)),name:labelFluid(name),hovertemplate:`${labelFluid(name)}: %{x:.1f}%<br>Depth: %{y:.1f} m<extra></extra>`})) as any} layout={{...layoutBase,autosize:true,xaxis:{title:"Probability (%)",range:[0,100],tickformat:".1f",showgrid:true},yaxis:{title:"Depth (m)",range:[depthRange[1],depthRange[0]],tickformat:".1f",showgrid:true},legend:{orientation:"h"}} as any} config={{responsive:true,displaylogo:false,scrollZoom:true,toImageButtonOptions:{format:"png",filename:"petroedge-fluid-probability",scale:2}}} style={{width:"100%",height:"92%"}} useResizeHandler/></Paper></Grid>
    <Grid item xs={12} lg={6}><Paper variant="outlined" sx={{p:1.5,height:470}}><Typography fontWeight={800}>Dominant fluid track</Typography><SafePlot data={[{type:"scatter",mode:"lines",x:plotRows.map(r=>fluidCode[String(r.fluid_type)]??-1),y:plotRows.map(r=>Number(r.depth)),line:{width:5},name:"Dominant fluid",text:plotRows.map(r=>labelFluid(String(r.fluid_type??"uncertain"))),customdata:plotRows.map(r=>Number(r.fluid_confidence??0)*100),hovertemplate:"Fluid: %{text}<br>Confidence: %{customdata:.1f}%<br>Depth: %{y:.1f} m<extra></extra>"}] as any} layout={{...layoutBase,autosize:true,xaxis:{title:"Fluid class",range:[-.5,3.5],tickvals:[0,1,2,3],ticktext:["Water","Oil","Gas","Residual HC"],tickangle:-20,showgrid:true},yaxis:{title:"Depth (m)",range:[depthRange[1],depthRange[0]],tickformat:".1f",showgrid:true}} as any} config={{responsive:true,displaylogo:false,scrollZoom:true,toImageButtonOptions:{format:"png",filename:"petroedge-fluid-track",scale:2}}} style={{width:"100%",height:"92%"}} useResizeHandler/></Paper></Grid>
   </Grid>

   {intervals.length>0&&<Paper variant="outlined" sx={{p:2.5}}><Typography variant="h6">Fluid interpretation by pay interval</Typography><TableContainer sx={{mt:1.5}}><Table size="small"><TableHead><TableRow><TableCell>Top depth</TableCell><TableCell>Base depth</TableCell><TableCell>Thickness</TableCell><TableCell>Predominant fluid</TableCell><TableCell>Confidence</TableCell><TableCell>Oil</TableCell><TableCell>Gas</TableCell><TableCell>Water</TableCell><TableCell>Mean φ</TableCell><TableCell>Mean Sw</TableCell></TableRow></TableHead><TableBody>{intervals.map((it:any,index)=><TableRow key={`${it.top_depth}-${index}`} hover><TableCell>{Number(it.top_depth).toFixed(1)} m</TableCell><TableCell>{Number(it.base_depth).toFixed(1)} m</TableCell><TableCell>{Number(it.gross_thickness??0).toFixed(1)} m</TableCell><TableCell><Chip size="small" label={labelFluid(String(it.primary_fluid??"uncertain"))}/></TableCell><TableCell>{pct(it.fluid_confidence)}</TableCell><TableCell>{pct(it.fluid_probabilities?.oil)}</TableCell><TableCell>{pct(it.fluid_probabilities?.gas)}</TableCell><TableCell>{pct(it.fluid_probabilities?.water)}</TableCell><TableCell>{pct(it.mean_porosity)}</TableCell><TableCell>{pct(it.mean_water_saturation)}</TableCell></TableRow>)}</TableBody></Table></TableContainer></Paper>}

   <Grid container spacing={2}>{tracks.map(t=><Grid item xs={12} md={6} xl={4} key={t.key}><Paper variant="outlined" sx={{p:1.5,height:430}}><Typography fontWeight={800}>{t.title} <Typography component="span" variant="caption" color="text.secondary">({t.unit})</Typography></Typography><SafePlot data={[{type:"scatter",mode:"lines",x:plotRows.map(r=>t.key==="hydrocarbon_probability"?Number(r[t.key])*100:Number(r[t.key])),y:plotRows.map(r=>Number(r.depth)),line:{width:1.5},name:t.title,hovertemplate:`${t.title}: %{x:.1f} ${t.unit}<br>Depth: %{y:.1f} m<extra></extra>`}] as any} layout={{...layoutBase,autosize:true,xaxis:{title:t.unit,type:t.log?"log":"linear",range:t.log?undefined:t.key==="hydrocarbon_probability"?[0,100]:t.range,tickformat:".1f",showgrid:true},yaxis:{title:"Depth (m)",range:[depthRange[1],depthRange[0]],tickformat:".1f",showgrid:true}} as any} config={{responsive:true,displaylogo:false,scrollZoom:true,modeBarButtonsToAdd:["drawline","drawrect","eraseshape"],toImageButtonOptions:{format:"png",filename:`petroedge-${t.key}`,scale:2}}} style={{width:"100%",height:"92%"}} useResizeHandler/></Paper></Grid>)}</Grid>
   <Paper variant="outlined" sx={{p:3}}><Stack direction="row" gap={1} alignItems="center"><Layers3/><Typography variant="h6">Interpretation limitations</Typography></Stack><Typography color="text.secondary" mt={1}>Water, oil and gas are now displayed separately at sample, track, probability and pay-interval levels. Classification is strongest when density, neutron, sonic and deep resistivity are all present. Production and PVT evidence should override log-only screening when available.</Typography></Paper>
  </>}
 </Stack>;
}
