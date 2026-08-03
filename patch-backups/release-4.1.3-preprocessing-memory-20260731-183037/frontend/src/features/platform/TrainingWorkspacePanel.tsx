import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogContentText,
  DialogTitle, Divider, FormControl, Grid, InputLabel, MenuItem, Paper, Select, Stack,
  Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Typography
} from "@mui/material";
import { BrainCircuit, Database, Download, Play, RefreshCcw, ShieldCheck, Trash2 } from "lucide-react";
import { DataPreparationStudio } from "./DataPreparationStudio";
import {
  deleteLifecycleModel, fetchDatasetPreview, fetchDatasets, fetchLifecycleAlgorithms, fetchLifecycleModels,
  type DatasetPreview, type DatasetSummary, type LifecycleAlgorithm, type LifecycleModel,
  type LifecyclePredictionResult,
  downloadPredictionFile, predictWithLifecycleModel, retrainLifecycleModel, trainLifecycleModel,
  updateLifecycleStage
} from "./platformApi";

const splitColumns=(value:string)=>value.split(",").map(v=>v.trim()).filter(Boolean);
const pretty=(value:string)=>value.replace(/_/g," ").replace(/\b\w/g,m=>m.toUpperCase());

export function TrainingWorkspacePanel(){
  const qc=useQueryClient();
  const [tab,setTab]=useState(0);
  const [datasetId,setDatasetId]=useState("");
  const [name,setName]=useState("PetroEdge registered model");
  const [algorithm,setAlgorithm]=useState<"random_forest"|"xgboost"|"ann">("random_forest");
  const [taskType,setTaskType]=useState<"regression"|"classification">("regression");
  const [target,setTarget]=useState("");
  const [features,setFeatures]=useState("");
  const [validation,setValidation]=useState<"random"|"grouped"|"temporal">("random");
  const [groupColumn,setGroupColumn]=useState("");
  const [timeColumn,setTimeColumn]=useState("");
  const [modelId,setModelId]=useState("");
  const [predictionDataset,setPredictionDataset]=useState("");
  const [deleteTarget,setDeleteTarget]=useState<LifecycleModel|null>(null);

  const datasets=useQuery<DatasetSummary[]>({queryKey:["platform","datasets"],queryFn:fetchDatasets});
  const algorithms=useQuery<{algorithms:LifecycleAlgorithm[]}>({queryKey:["lifecycle","algorithms"],queryFn:fetchLifecycleAlgorithms});
  const models=useQuery<{models:LifecycleModel[]}>({queryKey:["lifecycle","models"],queryFn:fetchLifecycleModels});
  const preview=useQuery<DatasetPreview>({queryKey:["dataset-preview",datasetId],queryFn:()=>fetchDatasetPreview(datasetId),enabled:Boolean(datasetId)});

  useEffect(()=>{if(!datasetId&&datasets.data?.length){setDatasetId(datasets.data[0].dataset_id);setPredictionDataset(datasets.data[0].dataset_id)}},[datasets.data,datasetId]);
  useEffect(()=>{if(!modelId&&models.data?.models.length)setModelId(models.data.models[0].model_id)},[models.data,modelId]);

  const train=useMutation({
    mutationFn:()=>trainLifecycleModel({
      display_name:name,dataset_id:datasetId,algorithm,task_type:taskType,
      target_column:target,feature_columns:splitColumns(features),
      validation_strategy:validation,
      group_column:validation==="grouped"?groupColumn:null,
      time_column:validation==="temporal"?timeColumn:null,
      test_size:.2,random_seed:42,hyperparameters:{}
    }),
    onSuccess:async()=>{await qc.invalidateQueries({queryKey:["lifecycle"]});setTab(1)}
  });
  const stage=useMutation({
    mutationFn:({id,next}:{id:string;next:string})=>updateLifecycleStage(id,next),
    onSuccess:()=>qc.invalidateQueries({queryKey:["lifecycle","models"]})
  });
  const predict=useMutation<LifecyclePredictionResult,Error,void>({
    mutationFn:()=>predictWithLifecycleModel({dataset_id:predictionDataset,model_id:modelId}),
    onSuccess:()=>setTab(2)
  });
  const retrain=useMutation({
    mutationFn:(id:string)=>retrainLifecycleModel(id,{dataset_id:datasetId}),
    onSuccess:()=>qc.invalidateQueries({queryKey:["lifecycle","models"]})
  });
  const remove=useMutation({
    mutationFn:(id:string)=>deleteLifecycleModel(id),
    onSuccess:async(_,deletedId)=>{
      setDeleteTarget(null);
      if(modelId===deletedId)setModelId("");
      await qc.invalidateQueries({queryKey:["lifecycle","models"]});
    }
  });

  const columns=preview.data?.columns??[];
  function submit(e:FormEvent){e.preventDefault();train.mutate()}

  return <Stack spacing={3}>
    <Box>
      <Stack direction="row" gap={1} alignItems="center"><BrainCircuit/><Typography variant="h5">Model Training and Lifecycle</Typography></Stack>
      <Typography color="text.secondary">Use CPU-ready built-in algorithms directly, or train, validate, register, version, deploy and reuse your own model artefacts.</Typography>
    </Box>
    <Tabs value={tab} onChange={(_,v)=>setTab(v)}>
      <Tab label="Data preparation"/><Tab label="Train model"/><Tab label="Model registry"/><Tab label="Predict dataset"/>
    </Tabs>

    {tab===0&&<DataPreparationStudio datasetId={datasetId} datasets={datasets.data??[]} onSelect={setDatasetId}/>}

    {tab===1&&<Grid container spacing={2}>
      <Grid item xs={12} lg={7}><Paper variant="outlined" sx={{p:3}}>
        <form onSubmit={submit}><Stack spacing={2}>
          <Typography variant="h6">Reproducible training configuration</Typography>
          <TextField label="Model family name" value={name} onChange={e=>setName(e.target.value)} required/>
          <FormControl><InputLabel>Dataset</InputLabel><Select label="Dataset" value={datasetId} onChange={e=>setDatasetId(e.target.value)}>
            {(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name} · {d.row_count??0} rows</MenuItem>)}
          </Select></FormControl>
          <Grid container spacing={2}><Grid item xs={12} md={6}><FormControl fullWidth><InputLabel>Algorithm</InputLabel><Select label="Algorithm" value={algorithm} onChange={e=>setAlgorithm(e.target.value as typeof algorithm)}>
            {(algorithms.data?.algorithms??[]).map(a=><MenuItem key={a.algorithm} value={a.algorithm} disabled={!a.available}>{a.display_name}{!a.available?" · unavailable":""}</MenuItem>)}
          </Select></FormControl></Grid><Grid item xs={12} md={6}><FormControl fullWidth><InputLabel>Task type</InputLabel><Select label="Task type" value={taskType} onChange={e=>setTaskType(e.target.value as typeof taskType)}><MenuItem value="regression">Regression</MenuItem><MenuItem value="classification">Classification</MenuItem></Select></FormControl></Grid></Grid>
          <TextField select label="Target column" value={target} onChange={e=>setTarget(e.target.value)}>{columns.map(c=><MenuItem key={c} value={c}>{c}</MenuItem>)}</TextField>
          <TextField label="Feature columns" helperText="Comma-separated columns, in the exact training order" value={features} onChange={e=>setFeatures(e.target.value)}/>
          <FormControl><InputLabel>Validation</InputLabel><Select label="Validation" value={validation} onChange={e=>setValidation(e.target.value as typeof validation)}><MenuItem value="random">Random holdout</MenuItem><MenuItem value="grouped">Grouped validation</MenuItem><MenuItem value="temporal">Temporal validation</MenuItem></Select></FormControl><Alert severity="info">{validation==="random"?"Random holdout randomly separates rows. Use only for independent single-well or non-correlated observations.":validation==="grouped"?"Grouped validation keeps entire wells or fields together, testing generalisation on unseen groups. Recommended for multi-well logs.":"Temporal validation trains on earlier depth/time samples and validates on later samples with a purge gap to reduce leakage."}</Alert>
          {validation==="grouped"&&<TextField select label="Group column" value={groupColumn} onChange={e=>setGroupColumn(e.target.value)}>{columns.map(c=><MenuItem key={c} value={c}>{c}</MenuItem>)}</TextField>}
          {validation==="temporal"&&<TextField select label="Time/depth column" value={timeColumn} onChange={e=>setTimeColumn(e.target.value)}>{columns.map(c=><MenuItem key={c} value={c}>{c}</MenuItem>)}</TextField>}
          <Stack direction="row" gap={1}><Chip icon={<ShieldCheck size={14}/>} label={`${pretty(validation)} validation`}/><Chip label="Seed 42"/><Chip label="Persistent artefact"/></Stack>
          {train.isError&&<Alert severity="error">{train.error instanceof Error?train.error.message:"Training failed."}</Alert>}
          <Button type="submit" variant="contained" startIcon={<Play/>} disabled={train.isPending||!datasetId||!target||splitColumns(features).length===0}>{train.isPending?"Training…":"Train and register model"}</Button>
        </Stack></form>
      </Paper></Grid>
      <Grid item xs={12} lg={5}><Paper variant="outlined" sx={{p:3}}><Typography variant="h6">Available columns</Typography><Typography variant="body2" color="text.secondary" mb={2}>Select one target and copy predictor names into the feature list.</Typography><Stack direction="row" gap={1} flexWrap="wrap">{columns.map(c=><Chip key={c} label={c} onClick={()=>setFeatures(v=>splitColumns(v).includes(c)?v:[...splitColumns(v),c].join(", "))}/>)}</Stack></Paper></Grid>
    </Grid>}

    {tab===2&&<Stack spacing={1.5}>
      {(models.data?.models??[]).map(m=><Paper key={m.model_id} variant="outlined" sx={{p:2.5}}>
        <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}>
          <Box><Typography fontWeight={800}>{m.display_name} · v{m.version}</Typography><Typography variant="body2" color="text.secondary">{pretty(m.algorithm)} · {pretty(m.task_type)} · {pretty(m.validation_strategy)}</Typography><Stack direction="row" gap={1} mt={1} flexWrap="wrap"><Chip size="small" label={m.stage} color={m.stage==="production"?"success":m.stage==="validated"?"primary":"default"}/>{Object.entries(m.metrics).map(([k,v])=><Chip key={k} size="small" variant="outlined" label={`${pretty(k)}: ${Number(v).toFixed(4)}`}/>)}</Stack></Box>
          <Stack direction="row" gap={1} flexWrap="wrap"><Button onClick={()=>stage.mutate({id:m.model_id,next:"validated"})}>Validate</Button><Button variant="contained" onClick={()=>stage.mutate({id:m.model_id,next:"production"})}>Deploy</Button><Button startIcon={<RefreshCcw size={15}/>} onClick={()=>retrain.mutate(m.model_id)}>Retrain</Button><Button color="error" startIcon={<Trash2 size={15}/>} onClick={()=>setDeleteTarget(m)}>Delete</Button></Stack>
        </Stack>
      </Paper>)}
      {!models.isLoading&&(models.data?.models.length??0)===0&&<Alert severity="info">No lifecycle models are registered yet.</Alert>}
    </Stack>}

    {tab===3&&<Grid container spacing={2}>
      <Grid item xs={12} md={5}><Paper variant="outlined" sx={{p:3}}><Stack spacing={2}><Typography variant="h6">Predict an uploaded dataset</Typography><FormControl><InputLabel>Registered model</InputLabel><Select label="Registered model" value={modelId} onChange={e=>setModelId(e.target.value)}>{(models.data?.models??[]).map(m=><MenuItem key={m.model_id} value={m.model_id}>{m.display_name} · v{m.version} · {m.stage}</MenuItem>)}</Select></FormControl><FormControl><InputLabel>Prediction dataset</InputLabel><Select label="Prediction dataset" value={predictionDataset} onChange={e=>setPredictionDataset(e.target.value)}>{(datasets.data??[]).map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl>{predict.isError&&<Alert severity="error">{predict.error instanceof Error?predict.error.message:"Prediction failed."}</Alert>}<Button variant="contained" startIcon={<Database/>} disabled={!modelId||!predictionDataset||predict.isPending} onClick={()=>predict.mutate()}>{predict.isPending?"Predicting…":"Run prediction"}</Button></Stack></Paper></Grid>
      <Grid item xs={12} md={7}><Paper variant="outlined" sx={{p:3,minHeight:300}}><Typography variant="h6">Prediction result</Typography>{predict.data?<Stack spacing={1.5} mt={2}><Alert severity="success">{predict.data.row_count} rows predicted. Output saved as {predict.data.output_path}.</Alert><Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="body2">Output column: <b>{predict.data.output_column}</b></Typography><Button startIcon={<Download size={16}/>} variant="outlined" onClick={()=>downloadPredictionFile(predict.data!.output_path)}>Download complete CSV</Button></Stack><Divider/>{predict.data.preview.length>0?<TableContainer sx={{maxHeight:440,border:1,borderColor:"divider",borderRadius:1}}><Table stickyHeader size="small"><TableHead><TableRow>{Object.keys(predict.data.preview[0]).map(column=><TableCell key={column} sx={{fontWeight:800,whiteSpace:"nowrap"}}>{column}</TableCell>)}</TableRow></TableHead><TableBody>{predict.data.preview.map((row,index)=><TableRow key={index} hover>{Object.keys(predict.data!.preview[0]).map(column=>{const value=row[column];return <TableCell key={column} sx={{whiteSpace:"nowrap"}}>{value===null||value===undefined?"—":typeof value==="number"?Number(value).toLocaleString(undefined,{maximumFractionDigits:6}):String(value)}</TableCell>})}</TableRow>)}</TableBody></Table></TableContainer>:<Alert severity="info">The prediction completed, but no preview rows were returned.</Alert>}<Typography variant="caption" color="text.secondary">Showing the first {predict.data.preview.length} rows. The complete result is stored in the output CSV.</Typography></Stack>:<Typography color="text.secondary" mt={2}>Select a registered model and any compatible uploaded dataset.</Typography>}</Paper></Grid>
    </Grid>}

    <Dialog open={Boolean(deleteTarget)} onClose={()=>!remove.isPending&&setDeleteTarget(null)} maxWidth="sm" fullWidth>
      <DialogTitle>Delete registered model?</DialogTitle>
      <DialogContent>
        <DialogContentText>This permanently removes <b>{deleteTarget?.display_name}</b>{deleteTarget?` · v${deleteTarget.version}`:""} from the registry and deletes its saved model artefacts. This action cannot be undone.</DialogContentText>
        {deleteTarget?.stage==="production"&&<Alert severity="warning" sx={{mt:2}}>This model is currently deployed to production.</Alert>}
        {remove.isError&&<Alert severity="error" sx={{mt:2}}>{remove.error instanceof Error?remove.error.message:"Model deletion failed."}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={()=>setDeleteTarget(null)} disabled={remove.isPending}>Cancel</Button>
        <Button color="error" variant="contained" startIcon={<Trash2 size={16}/>} disabled={!deleteTarget||remove.isPending} onClick={()=>deleteTarget&&remove.mutate(deleteTarget.model_id)}>{remove.isPending?"Deleting…":"Delete model"}</Button>
      </DialogActions>
    </Dialog>
  </Stack>
}
