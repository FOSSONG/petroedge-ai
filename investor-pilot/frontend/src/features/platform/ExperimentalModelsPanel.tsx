import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {Alert,Button,MenuItem,Paper,Stack,Table,TableBody,TableCell,TableContainer,TableHead,TableRow,TextField,Typography} from "@mui/material";
import {apiRequest} from "../../api/http";
type Variant={name:string;missing_curve:string|null;required_features:string[];validation_mae:number;mae_change_vs_full_percent:number|null};
type Dataset={dataset_id:string;name:string;training_rows:number;validation_rows:number;test_rows_excluded:number;error_unit:string;variants:Variant[]};
type Report={configured:boolean;design:string;datasets:Dataset[]};
export function ExperimentalModelsPanel(){
 const [selected,setSelected]=useState("");
 const q=useQuery({queryKey:["experimental-comparison"],queryFn:()=>apiRequest<Report>("/training-lifecycle/experimental-comparison"),retry:false});
 const current=q.data?.datasets.find(d=>d.dataset_id===selected)??q.data?.datasets[0];
 return <Paper variant="outlined" sx={{p:3}}><Stack spacing={2}>
  <Typography variant="h6">Experimental missing curve models</Typography>
  <Alert severity="warning">Administrator review only. These models are not deployed and cannot be selected for customer predictions. Lower development error does not establish accuracy on new wells.</Alert>
  <Button disabled={q.isFetching} onClick={()=>void q.refetch()}>{q.isFetching?"Loading comparisons...":"Refresh comparisons"}</Button>
  {q.isError&&<Alert severity="error">{q.error.message}</Alert>}
  {q.data&&<Typography>{q.data.design}</Typography>}
  {q.data&&!q.data.datasets.length&&<Alert severity="info">No experiment datasets are available.</Alert>}
  {current&&<><TextField select label="Experimental target and condition" value={current.dataset_id} onChange={e=>setSelected(e.target.value)}>{q.data!.datasets.map(d=><MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</TextField>
  <Typography>{current.training_rows} training rows; {current.validation_rows} validation rows; {current.test_rows_excluded} prior test rows excluded. Error unit: {current.error_unit}.</Typography>
  <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Omitted measurement</TableCell><TableCell>Required inputs</TableCell><TableCell>Validation MAE</TableCell><TableCell>Error change versus full inputs</TableCell></TableRow></TableHead><TableBody>{current.variants.map(v=><TableRow key={v.name}><TableCell>{v.missing_curve??"None"}</TableCell><TableCell>{v.required_features.join(", ")}</TableCell><TableCell>{v.validation_mae.toPrecision(4)}</TableCell><TableCell>{v.mae_change_vs_full_percent===null?"Not defined":`${v.mae_change_vs_full_percent.toFixed(1)}%`}</TableCell></TableRow>)}</TableBody></Table></TableContainer>
  <Typography variant="caption">MAE means mean absolute error; lower is better on this validation set only. Positive change means higher error. Each omitted-curve variant was trained separately without imputing that curve. DT was not required; combinations missing two or more required curves were not tested.</Typography></>}
 </Stack></Paper>
}
