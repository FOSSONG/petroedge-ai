import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, InputLabel, MenuItem, Paper, Select, Stack, TextField, Typography } from "@mui/material";
import { FlaskConical, Plus, RefreshCw, Timer, Trophy } from "lucide-react";
import { SafePlot } from "../../components/SafePlot";
import { createExperiment, fetchDatasets, fetchExperiments } from "./platformApi";

const tasks = ["hydrocarbon_classification","fluid_type_classification","lithology_classification","reservoir_quality_classification","pay_zone_classification","porosity_regression","permeability_regression","water_saturation_regression","anomaly_detection"];
const algorithms = ["XGBoost", "Random Forest", "LightGBM", "CatBoost", "ANN", "CNN", "Transformer"];
const pretty = (value: string) => value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
const finite = (value: unknown): number | null => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; };

export function ExperimentManagerPanel() {
  const queryClient = useQueryClient();
  const [open,setOpen]=useState(false); const [name,setName]=useState(""); const [task,setTask]=useState(tasks[0]); const [algorithm,setAlgorithm]=useState(algorithms[0]); const [datasetId,setDatasetId]=useState("");
  const query=useQuery({queryKey:["platform","experiments"],queryFn:fetchExperiments,retry:1});
  const datasets=useQuery({queryKey:["platform","datasets"],queryFn:fetchDatasets});
  const mutation=useMutation({mutationFn:()=>createExperiment({name,task,algorithm,dataset_id:datasetId||null,validation_strategy:"grouped_by_well"}),onSuccess:async()=>{await queryClient.invalidateQueries({queryKey:["platform","experiments"]});setOpen(false);setName("");}});
  const submit=(event:FormEvent)=>{event.preventDefault();if(name.trim())mutation.mutate();};

  const experiments = Array.isArray(query.data) ? query.data : [];
  const metricRows = useMemo(() => experiments.flatMap((experiment) => {
    const metrics = experiment.metrics && typeof experiment.metrics === "object" && !Array.isArray(experiment.metrics) ? experiment.metrics : {};
    return Object.entries(metrics).map(([metric, value]) => ({ experiment: experiment.name || experiment.experiment_id, metric: pretty(metric), value: finite(value) })).filter((row): row is {experiment:string;metric:string;value:number} => row.value !== null);
  }), [experiments]);
  const selectedMetrics = Array.from(new Set(metricRows.map((row) => row.metric))).slice(0, 6);
  const plotData = selectedMetrics.map((metric) => ({ type: "bar", name: metric, x: metricRows.filter((row) => row.metric===metric).map((row)=>row.experiment), y: metricRows.filter((row)=>row.metric===metric).map((row)=>row.value), hovertemplate: `${metric}: %{y:.3f}<extra></extra>` }));
  const plotLayout = { height: 460, autosize: true, barmode: "group", margin: { l: 60, r: 20, t: 45, b: 100 }, title: { text: "Cross-model evaluation metrics" }, xaxis: { tickangle: -25 }, yaxis: { title: { text: "Metric value" }, tickformat: ".3f" }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)" };

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["platform", "experiments"] });

  return <Stack spacing={3}>
    <Stack direction={{xs:"column",sm:"row"}} justifyContent="space-between" gap={2}>
      <Box><Stack direction="row" gap={1} alignItems="center"><FlaskConical size={24}/><Typography variant="h5">Model Evaluation Centre</Typography></Stack><Typography variant="body2" color="text.secondary">Validated metrics from reproducible PetroEdge AI MVP experiments.</Typography></Box>
      <Stack direction="row" gap={1}><Button variant="outlined" startIcon={<RefreshCw size={16}/>} onClick={refresh}>Refresh</Button><Button variant="contained" startIcon={<Plus size={17}/>} onClick={()=>setOpen(true)}>New experiment</Button></Stack>
    </Stack>

    {query.isLoading && <Stack alignItems="center" py={6}><CircularProgress/><Typography mt={1} color="text.secondary">Loading evaluation records…</Typography></Stack>}
    {query.isError && <Alert severity="error">{query.error instanceof Error ? query.error.message : "Unable to load model evaluation records."}</Alert>}

    {!query.isLoading && experiments.length===0 && <Paper variant="outlined" sx={{p:5,textAlign:"center"}}><FlaskConical size={42}/><Typography variant="h6" mt={1}>No experiments registered</Typography><Typography color="text.secondary" mt={.5}>Create an experiment or complete a training run to populate evaluation metrics.</Typography></Paper>}

    {metricRows.length>0 && <Paper variant="outlined" sx={{p:1.5}}><SafePlot data={plotData} layout={plotLayout} minHeight={460}/></Paper>}
    {experiments.length>0 && metricRows.length===0 && <Alert severity="info">Experiments are registered, but no numeric evaluation metrics have been stored yet.</Alert>}

    <Stack spacing={1.5}>{experiments.map((experiment) => {
      const metrics = experiment.metrics && typeof experiment.metrics === "object" && !Array.isArray(experiment.metrics) ? experiment.metrics : {};
      return <Paper key={experiment.experiment_id} variant="outlined" sx={{p:2.25}}><Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}><Box><Stack direction="row" gap={1} alignItems="center"><Typography variant="h6">{experiment.name || "Unnamed experiment"}</Typography><Chip size="small" label={experiment.status || "unknown"} color={experiment.status==="completed"?"success":experiment.status==="failed"?"error":"default"}/></Stack><Typography variant="body2" color="text.secondary">{pretty(experiment.task || "unspecified task")} · {experiment.algorithm || "Unspecified algorithm"}</Typography></Box><Stack direction="row" gap={3}><Box><Typography variant="caption" color="text.secondary">Validation</Typography><Typography variant="body2">{experiment.validation_strategy||"Not set"}</Typography></Box><Box><Typography variant="caption" color="text.secondary">Metrics</Typography><Typography variant="body2">{Object.keys(metrics).length||"—"}</Typography></Box>{finite(experiment.training_seconds)!==null&&<Box><Typography variant="caption" color="text.secondary">Duration</Typography><Stack direction="row" gap={.5} alignItems="center"><Timer size={15}/><Typography variant="body2">{finite(experiment.training_seconds)?.toFixed(1)}s</Typography></Stack></Box>}</Stack></Stack>{Object.keys(metrics).length>0&&<Stack direction="row" gap={1} mt={2} flexWrap="wrap">{Object.entries(metrics).map(([key,value])=><Chip key={key} icon={<Trophy size={14}/>} label={`${pretty(key)}: ${finite(value)?.toFixed(3) ?? String(value)}`} size="small" variant="outlined"/>)}</Stack>}</Paper>;
    })}</Stack>

    <Dialog open={open} onClose={()=>setOpen(false)} fullWidth maxWidth="sm"><form onSubmit={submit}><DialogTitle>Create experiment</DialogTitle><DialogContent><Stack spacing={2} mt={1}><TextField label="Experiment name" required value={name} onChange={(event)=>setName(event.target.value)}/><FormControl><InputLabel>Task</InputLabel><Select label="Task" value={task} onChange={(event)=>setTask(event.target.value)}>{tasks.map((value)=><MenuItem key={value} value={value}>{pretty(value)}</MenuItem>)}</Select></FormControl><FormControl><InputLabel>Algorithm</InputLabel><Select label="Algorithm" value={algorithm} onChange={(event)=>setAlgorithm(event.target.value)}>{algorithms.map((value)=><MenuItem key={value} value={value}>{value}</MenuItem>)}</Select></FormControl><FormControl><InputLabel>Dataset</InputLabel><Select label="Dataset" value={datasetId} onChange={(event)=>setDatasetId(event.target.value)}><MenuItem value="">No dataset selected</MenuItem>{(datasets.data??[]).map((dataset)=><MenuItem key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name}</MenuItem>)}</Select></FormControl>{mutation.isError&&<Alert severity="error">{mutation.error instanceof Error?mutation.error.message:"Creation failed."}</Alert>}</Stack></DialogContent><DialogActions><Button onClick={()=>setOpen(false)}>Cancel</Button><Button type="submit" variant="contained" disabled={!name.trim()||mutation.isPending}>{mutation.isPending?"Creating…":"Create"}</Button></DialogActions></form></Dialog>
  </Stack>;
}
