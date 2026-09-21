import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { apiRequest } from "../../api/http";
import type { DatasetSummary } from "./platformApi";
const units:Record<string,string[]>={depth_m:["m","ft"],gamma_ray_api:["API"],resistivity_ohmm:["ohm.m"],density_gcc:["g/cm3","kg/m3"],neutron_porosity_vv:["v/v","%"],sonic_usft:["us/ft","us/m"],caliper_in:["in","cm","mm"]};
const sourceUnits:Record<string,string>={M:"m",FT:"ft",GAPI:"API",API:"API",OHMM:"ohm.m","OHM.M":"ohm.m","G/C3":"g/cm3","G/CC":"g/cm3","G/CM3":"g/cm3","KG/M3":"kg/m3","V/V":"v/v",PU:"%","%":"%","US/F":"us/ft","US/FT":"us/ft","US/M":"us/m",INCHES:"in",IN:"in",CM:"cm",MM:"mm"};
export function CurveMappingCopyPanel({id,mapping,declaredUnits,onSelect}:{id:string;mapping:Record<string,string|null>;declaredUnits:Record<string,string>;onSelect:(id:string)=>void}) {
 const client=useQueryClient();
 const unitFor=(target:string,source:string)=>{const declared=sourceUnits[(declaredUnits[source]??"").trim().toUpperCase()];return declared&&units[target].includes(declared)?declared:"";};
 const [choices,setChoices]=useState<Record<string,{source:string;unit:string}>>(()=>Object.fromEntries(Object.keys(units).map(target=>{const candidates=Object.keys(mapping).filter(source=>mapping[source]===target);const source=candidates.length===1?candidates[0]:"";return [target,{source,unit:unitFor(target,source)}];})));
 const [nulls,setNulls]=useState("-999.25, -999, -9999, -99999");
 const selected=Object.entries(choices).filter(([,choice])=>choice.source);
 const markers=nulls.split(",").map(s=>s.trim()).filter(Boolean).map(Number);
 const valid=Boolean(choices.depth_m.source)&&selected.every(([,c])=>c.unit)&&markers.every(Number.isFinite)&&new Set(selected.map(([,c])=>c.source)).size===selected.length;
 const save=useMutation({mutationFn:()=>apiRequest<DatasetSummary>(`/datasets/${id}/mapped-copy`,{method:"POST",body:JSON.stringify({version:1,depth_reference:"MD",curves:Object.fromEntries(selected.map(([target,choice])=>[target,{...choice,null_values:markers}]))})}),onSuccess:async data=>{await client.invalidateQueries({queryKey:["platform","datasets"]});onSelect(data.dataset_id);}});
 return <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
  <Typography variant="h6">Resolve aliases and source units</Typography>
  <Typography>Choose the measured-depth curve and the source for each quantity. Duplicate candidates are left unselected. This creates a separate copy with converted units and recorded mapping; your original LAS is preserved. Sonic and caliper are optional for reservoir screening.</Typography>
  {Object.entries(units).map(([target,options])=><Grid container spacing={2} key={target}><Grid item xs={12} md={8}><TextField select fullWidth label={`${target} source`} value={choices[target].source} onChange={e=>setChoices(old=>({...old,[target]:{source:e.target.value,unit:unitFor(target,e.target.value)}}))}><MenuItem value="">Unmapped / unavailable</MenuItem>{Object.keys(mapping).map(source=><MenuItem key={source} value={source}>{source} {declaredUnits[source]?`[${declaredUnits[source]}]`:"[unit missing]"}</MenuItem>)}</TextField></Grid><Grid item xs={12} md={4}><TextField select fullWidth label={`${target} source unit`} value={choices[target].unit} disabled={!choices[target].source} onChange={e=>setChoices(old=>({...old,[target]:{...old[target],unit:e.target.value}}))}><MenuItem value="">Select unit</MenuItem>{options.map(unit=><MenuItem key={unit} value={unit}>{unit}</MenuItem>)}</TextField></Grid></Grid>)}
  <TextField label="Source null markers" value={nulls} onChange={e=>setNulls(e.target.value)} helperText="Comma-separated; zero remains a real value unless explicitly listed."/>
  <Alert severity="info">Depth reference: measured depth (MD). Do not select TVD/TVDSS here; those require a trajectory conversion. Missing source curves stay missing.</Alert>
  <Button variant="contained" disabled={!valid||save.isPending} onClick={()=>save.mutate()}>{save.isPending?"Saving mapped copy...":"Create mapped interpretation copy"}</Button>
  {save.isError&&<Alert severity="error">{save.error.message}</Alert>}
 </Stack></Paper>;
}
