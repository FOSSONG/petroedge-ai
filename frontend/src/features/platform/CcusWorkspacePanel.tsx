import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Box,Button,Checkbox,Chip,CircularProgress,FormControl,FormControlLabel,Grid,InputLabel,LinearProgress,MenuItem,Paper,Select,Stack,TextField,Typography} from "@mui/material";
import {Database,RefreshCw,Trash2} from "lucide-react";
import {createCcusScreen,deleteCcusRun,fetchCcusCapabilities,fetchCcusRuns,fetchDatasets,type CcusScreenPayload} from "./platformApi";
const n=(v:string,f=0)=>Number.isFinite(Number(v))?Number(v):f;
const colour=(s:number):"success"|"warning"|"error"=>s>=75?"success":s>=55?"warning":"error";

export function CcusWorkspacePanel(){
 const qc=useQueryClient();
 const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const caps=useQuery({queryKey:["ccus","capabilities"],queryFn:fetchCcusCapabilities});
 const runs=useQuery({queryKey:["ccus","runs"],queryFn:fetchCcusRuns});
 const [dataset,setDataset]=useState(""); const [name,setName]=useState("Niger Delta CCUS screening");
 const [type,setType]=useState<"saline_aquifer"|"depleted_reservoir">("saline_aquifer");
 const [area,setArea]=useState("10"),[h,setH]=useState("35"),[phi,setPhi]=useState("0.20"),[rho,setRho]=useState("650");
 const [eff,setEff]=useState("0.02"),[perm,setPerm]=useState("100"),[depth,setDepth]=useState("1800");
 const [pi,setPi]=useState("18"),[pf,setPf]=useState("28"),[seal,setSeal]=useState("40");
 const [fault,setFault]=useState<"low"|"medium"|"high"|"unknown">("unknown");
 const [pressureData,setPressureData]=useState(false),[sealData,setSealData]=useState(false),[faultData,setFaultData]=useState(false),[geo,setGeo]=useState(false);
 useEffect(()=>{if(!dataset&&datasets.data?.[0]?.dataset_id)setDataset(datasets.data[0].dataset_id)},[dataset,datasets.data]);
 const payload=useMemo<CcusScreenPayload>(()=>({dataset_id:dataset||null,project_name:name.trim(),storage_type:type,area_km2:n(area),net_thickness_m:n(h),porosity_fraction:n(phi),co2_density_kg_m3:n(rho),storage_efficiency_fraction:n(eff),permeability_md:n(perm),depth_m:n(depth),initial_pressure_mpa:n(pi),fracture_pressure_mpa:n(pf),caprock_thickness_m:seal.trim()?n(seal):null,fault_risk:fault,pressure_data_available:pressureData,seal_data_available:sealData,fault_data_available:faultData,geomechanics_available:geo}),[dataset,name,type,area,h,phi,rho,eff,perm,depth,pi,pf,seal,fault,pressureData,sealData,faultData,geo]);
 const create=useMutation({mutationFn:()=>createCcusScreen(payload),onSuccess:()=>qc.invalidateQueries({queryKey:["ccus","runs"]})});
 const remove=useMutation({mutationFn:deleteCcusRun,onSuccess:()=>qc.invalidateQueries({queryKey:["ccus","runs"]})});
 const latest=create.data??runs.data?.[0]; const valid=name.trim().length>1&&payload.area_km2>0&&payload.net_thickness_m>0&&payload.porosity_fraction>0&&payload.storage_efficiency_fraction>0&&payload.depth_m>0;
 if(datasets.isLoading||caps.isLoading)return <LinearProgress/>;
 return <Stack spacing={3}>
  <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}>
   <Box><Typography variant="h4" fontWeight={850}>CCUS Screening</Typography><Typography color="text.secondary">Transparent volumetric storage-capacity screening with injectivity, containment and evidence-quality diagnostics.</Typography></Box>
   <Stack direction="row" gap={1}><Chip icon={<Database size={16}/>} label={`${datasets.data?.length??0} datasets`}/><Chip color="success" label={caps.data?.status??"operational"}/><Button variant="outlined" startIcon={<RefreshCw size={16}/>} onClick={()=>void runs.refetch()}>Refresh</Button></Stack>
  </Stack>
  <Alert severity="info">Capacity uses MCOâ‚‚ = area Ã— net thickness Ã— porosity Ã— storage efficiency Ã— in-situ COâ‚‚ density. Results are screening estimates, not dynamic simulation or regulatory storage classification.</Alert>
  <Grid container spacing={2}>
   <Grid item xs={12} lg={7}><Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
    <Typography variant="h6">Screening inputs</Typography>
    <Stack direction={{xs:"column",md:"row"}} gap={2}><TextField fullWidth label="Project name" value={name} onChange={e=>setName(e.target.value)}/><FormControl fullWidth><InputLabel>Dataset</InputLabel><Select label="Dataset" value={dataset} onChange={e=>setDataset(e.target.value)}><MenuItem value="">No dataset link</MenuItem>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl></Stack>
    <FormControl><InputLabel>Storage setting</InputLabel><Select label="Storage setting" value={type} onChange={e=>setType(e.target.value as typeof type)}><MenuItem value="saline_aquifer">Saline aquifer</MenuItem><MenuItem value="depleted_reservoir">Depleted reservoir</MenuItem></Select></FormControl>
    <Grid container spacing={2}>{[
      ["Area (kmÂ²)",area,setArea],["Net thickness (m)",h,setH],["Porosity (fraction)",phi,setPhi],["COâ‚‚ density (kg/mÂ³)",rho,setRho],
      ["Storage efficiency",eff,setEff],["Permeability (mD)",perm,setPerm],["Depth (m)",depth,setDepth],["Initial pressure (MPa)",pi,setPi],
      ["Fracture pressure (MPa)",pf,setPf],["Caprock thickness (m)",seal,setSeal]
    ].map(([label,value,setter])=><Grid item xs={12} sm={6} md={4} key={label as string}><TextField fullWidth type="number" label={label as string} value={value as string} onChange={e=>(setter as (v:string)=>void)(e.target.value)}/></Grid>)}
    <Grid item xs={12} sm={6} md={4}><FormControl fullWidth><InputLabel>Fault risk</InputLabel><Select label="Fault risk" value={fault} onChange={e=>setFault(e.target.value as typeof fault)}>{["unknown","low","medium","high"].map(x=><MenuItem key={x} value={x}>{x}</MenuItem>)}</Select></FormControl></Grid></Grid>
    <Box><Typography variant="subtitle2">Available evidence</Typography><Stack direction={{xs:"column",sm:"row"}} flexWrap="wrap">
     <FormControlLabel control={<Checkbox checked={pressureData} onChange={e=>setPressureData(e.target.checked)}/>} label="Pressure"/>
     <FormControlLabel control={<Checkbox checked={sealData} onChange={e=>setSealData(e.target.checked)}/>} label="Seal"/>
     <FormControlLabel control={<Checkbox checked={faultData} onChange={e=>setFaultData(e.target.checked)}/>} label="Fault"/>
     <FormControlLabel control={<Checkbox checked={geo} onChange={e=>setGeo(e.target.checked)}/>} label="Geomechanics"/>
    </Stack></Box>
    {create.isError&&<Alert severity="error">{create.error instanceof Error?create.error.message:"Screening failed."}</Alert>}
    <Button variant="contained" size="large" disabled={!valid||create.isPending} onClick={()=>create.mutate()}>{create.isPending?"Calculatingâ€¦":"Run CCUS screening"}</Button>
   </Stack></Paper></Grid>
   <Grid item xs={12} lg={5}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6" mb={2}>Latest result</Typography>
    {!latest&&<Typography color="text.secondary">Run a screening calculation to generate results.</Typography>}
    {latest&&<Stack spacing={2}><Stack direction="row" justifyContent="space-between"><Box><Typography variant="overline">Estimated capacity</Typography><Typography variant="h3" fontWeight={900}>{latest.capacity_mt.toLocaleString()} Mt</Typography></Box><Chip color={colour(latest.suitability_score)} label={latest.suitability_class}/></Stack>
    <Grid container spacing={1.5}>{[["Suitability",latest.suitability_score],["Injectivity",latest.injectivity_score],["Containment",latest.containment_score],["Data quality",latest.data_quality_score]].map(([l,s])=><Grid item xs={6} key={l as string}><Paper variant="outlined" sx={{p:1.5}}><Typography variant="caption">{l as string}</Typography><Typography variant="h6">{Number(s).toFixed(1)}%</Typography></Paper></Grid>)}</Grid>
    <Typography>Pressure margin: <strong>{latest.pressure_margin_mpa.toFixed(2)} MPa</strong></Typography>
    {latest.risk_flags.length>0&&<Alert severity="warning">{latest.risk_flags.map(x=><Typography key={x} variant="body2">â€¢ {x}</Typography>)}</Alert>}
    <Box><Typography variant="subtitle2">Recommended actions</Typography>{latest.recommendations.map(x=><Typography key={x} variant="body2" mt={.7}>â€¢ {x}</Typography>)}</Box>
    </Stack>}</Paper></Grid>
  </Grid>
  <Paper variant="outlined" sx={{p:3}}><Stack direction="row" justifyContent="space-between" mb={2}><Typography variant="h6">Auditable screening history</Typography><Chip label={`${runs.data?.length??0} runs`}/></Stack>
   {runs.isLoading&&<CircularProgress size={24}/>}<Stack spacing={1.5}>{(runs.data??[]).map(r=><Paper key={r.run_id} variant="outlined" sx={{p:2}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between"><Box><Typography fontWeight={800}>{r.project_name}</Typography><Typography variant="body2" color="text.secondary">{r.dataset_name??"No linked dataset"} Â· {r.storage_type.replace(/_/g," ")} Â· {new Date(r.created_at).toLocaleString()}</Typography></Box><Stack direction="row" gap={1}><Chip label={`${r.capacity_mt.toLocaleString()} Mt`}/><Chip color={colour(r.suitability_score)} label={`${r.suitability_score.toFixed(1)}%`}/><Button size="small" color="error" startIcon={<Trash2 size={15}/>} onClick={()=>remove.mutate(r.run_id)}>Delete</Button></Stack></Stack></Paper>)}</Stack>
  </Paper>
 </Stack>
}