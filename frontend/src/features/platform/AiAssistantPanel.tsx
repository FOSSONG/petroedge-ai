import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, FormControl, Grid, InputLabel, LinearProgress, MenuItem, Paper, Select, Stack, TextField, Typography } from "@mui/material";
import { Bot, Send, Sparkles } from "lucide-react";
import { askAssistant, fetchDatasets } from "./platformApi";

const suggestions=["Summarise this reservoir","Show all pay intervals and their depths","Which interval has the highest porosity?","Which curve contributed most to the hydrocarbon prediction?","Explain why the strongest interval is classified as pay","Describe the lithology distribution"];
export function AiAssistantPanel(){
 const ds=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
 const [chosen,setChosen]=useState(""); const id=chosen||(ds.data?.[0]?.dataset_id??"");
 const [question,setQuestion]=useState("");
 const m=useMutation({mutationFn:(q:string)=>askAssistant(id,q)});
 useEffect(()=>{m.reset();},[id]);
 const submit=(q=question)=>{if(id&&q.trim()){setQuestion(q);m.mutate(q.trim());}};
 return <Stack spacing={3}>
  <Paper className="feature-hero" sx={{p:{xs:3,md:4}}}><Box sx={{position:"relative",zIndex:1}}><Stack direction="row" gap={1.2} alignItems="center"><Bot/><Typography variant="h4" fontWeight={900}>Petroleum-domain AI Assistant</Typography></Stack><Typography mt={1}>Evidence-grounded answers generated from the selected dataset, its interpreted samples and detected pay intervals.</Typography></Box></Paper>
  <FormControl fullWidth><InputLabel id="assistant-dataset-label">Dataset</InputLabel><Select labelId="assistant-dataset-label" label="Dataset" value={id} onChange={e=>setChosen(e.target.value)}>{(ds.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl>
  <Stack direction="row" gap={1} flexWrap="wrap">{suggestions.map(q=><Chip key={q} icon={<Sparkles size={14}/>} label={q} onClick={()=>submit(q)} clickable/>)}</Stack>
  <TextField multiline minRows={3} label="Ask a dataset-specific question" value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();submit();}}}/>
  <Button variant="contained" startIcon={<Send/>} onClick={()=>submit()} disabled={!id||!question.trim()||m.isPending}>{m.isPending?"Analysing dataset…":"Analyse evidence"}</Button>
  {m.isPending&&<LinearProgress/>}{m.isError&&<Alert severity="error">{m.error instanceof Error?m.error.message:"Assistant request failed."}</Alert>}
  {m.data&&<Grid container spacing={2}>
   <Grid item xs={12} lg={7}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="overline">Intent: {m.data.intent.replace(/_/g," ")}</Typography><Typography variant="h6">PetroEdge response</Typography><Typography mt={1.5}>{m.data.answer}</Typography><Typography variant="subtitle2" mt={2}>Evidence used</Typography>{m.data.evidence.map(x=><Typography key={x}>• {x}</Typography>)}<Alert severity="info" sx={{mt:2}}>Decision support only. Validate against core, pressure, test and production evidence.</Alert></Paper></Grid>
   <Grid item xs={12} lg={5}><Paper variant="outlined" sx={{p:3,height:"100%"}}><Typography variant="h6">Explainable prediction</Typography><Stack direction="row" gap={1} flexWrap="wrap" mt={1}><Chip color={m.data.explanation.prediction==="Pay"?"success":"default"} label={m.data.explanation.prediction}/><Chip label={`${m.data.explanation.depth.toFixed(2)} m`}/><Chip label={m.data.explanation.lithology}/></Stack><Typography mt={2}>Confidence {(m.data.explanation.confidence*100).toFixed(1)}%</Typography><LinearProgress variant="determinate" value={m.data.explanation.confidence*100} sx={{height:9,borderRadius:5,mt:.5}}/><Typography mt={1}>Porosity {(m.data.explanation.porosity*100).toFixed(1)}% · Sw {(m.data.explanation.water_saturation*100).toFixed(1)}%</Typography><Typography variant="subtitle2" mt={2}>Contributing evidence</Typography>{m.data.explanation.feature_importance.map(item=><Box key={item.feature} mt={1}><Stack direction="row" justifyContent="space-between"><Typography variant="body2">{item.feature}</Typography><Typography variant="body2">{(item.contribution*100).toFixed(1)}%</Typography></Stack><LinearProgress variant="determinate" value={item.contribution*100}/></Box>)}</Paper></Grid>
  </Grid>}
 </Stack>;
}
