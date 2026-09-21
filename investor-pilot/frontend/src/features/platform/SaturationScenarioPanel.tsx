import {useState} from "react";
import {Alert,Button,Grid,Paper,Stack,TextField,Typography} from "@mui/material";
import {archieScenario,ArchieInputs} from "./archieScenario";
const defaults={phi:"0.20",rt:"10",rw:"0.10",a:"1",m:"2",n:"2"};
const labels:Record<keyof ArchieInputs,string>={phi:"Porosity (fraction)",rt:"Formation resistivity Rt (ohm.m)",rw:"Water resistivity Rw (ohm.m)",a:"Archie a",m:"Cementation exponent m",n:"Saturation exponent n"};
export function SaturationScenarioPanel(){
 const [values,setValues]=useState(defaults);const [temperature,setTemperature]=useState("");const [basis,setBasis]=useState("");
 let result:ReturnType<typeof archieScenario>|undefined;let error="";
 try{const p=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,v.trim()===""?NaN:Number(v)])) as ArchieInputs;result=archieScenario(p)}catch(e){error=e instanceof Error?e.message:"Invalid parameters"}
 const exportScenario=()=>{if(!result)return;const payload={kind:"manual_uncalibrated_archie_scenario",source:"Manually entered values; not linked to the selected dataset",inputs:values,rw_temperature_context:temperature||"Unspecified",parameter_basis:basis||"Assumed example values",formula:"Sw = (a * Rw / (Rt * phi^m))^(1/n)",raw_water_fraction:result.raw,bounded_display_water_fraction:result.bounded,above_one:result.aboveOne,trained_model:false,oil_gas_split_available:false};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download="petroedge-archie-scenario.json";document.body.appendChild(link);link.click();link.remove();window.setTimeout(()=>URL.revokeObjectURL(url),10000)};
 return <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
 <Typography variant="h6">Manual saturation scenario</Typography>
 <Alert severity="warning">Uncalibrated clean-formation Archie calculation, not a trained prediction. The defaults are examples. Values are entered manually and are not taken from the selected dataset. Shaly formations require a justified interpretation method.</Alert>
 <Typography>Sw = (a ? Rw / (Rt ? porosity^m))^(1/n). Rw must correspond to the relevant formation temperature; no temperature correction is performed here.</Typography>
 <Grid container spacing={2}>{(Object.keys(labels) as (keyof ArchieInputs)[]).map(k=><Grid item xs={12} sm={6} md={4} key={k}><TextField fullWidth label={labels[k]} type="number" inputProps={{step:"any"}} value={values[k]} onChange={e=>setValues(v=>({...v,[k]:e.target.value}))}/></Grid>)}</Grid>
 <TextField label="Rw temperature context" placeholder="For example: assumed at 80 C; not measured" value={temperature} onChange={e=>setTemperature(e.target.value)}/>
 <TextField label="Parameter source or assumption" value={basis} onChange={e=>setBasis(e.target.value)}/>
 {error&&<Alert severity="error">{error}</Alert>}
 {result&&<><Typography role="status">Raw calculated Sw: {(100*result.raw).toFixed(2)}%. Bounded display: {(100*result.bounded).toFixed(2)}%.</Typography>{result.aboveOne&&<Alert severity="error">Calculated Sw exceeds 100%. Review inputs and model applicability. The raw value is retained; the bounded display does not validate it.</Alert>}</>}
 <Typography>No oil/gas split or gas probability is inferred from this calculation. It does not update reservoir plots, saved analyses or model predictions.</Typography>
 <Stack direction="row" spacing={2}><Button disabled={!result} onClick={exportScenario}>Download scenario JSON</Button><Button onClick={()=>{setValues(defaults);setTemperature("");setBasis("")}}>Reset example</Button></Stack>
 </Stack></Paper>
}
