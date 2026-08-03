import {useEffect,useMemo,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {Alert,Button,Checkbox,Dialog,DialogActions,DialogContent,DialogTitle,FormControl,FormControlLabel,Grid,InputLabel,MenuItem,Paper,Select,Stack,Table,TableBody,TableCell,TableContainer,TableHead,TableRow,TextField,Tooltip,Typography} from "@mui/material";
import {ChevronLeft,ChevronRight,Clipboard,Download,Plus,Save,ShieldCheck,Trash2} from "lucide-react";
import {downloadDatasetFile,editDataset,fetchDatasetPreview,fetchDatasetQuality,prepareDataset,type DatasetSummary} from "./platformApi";

const PAGE_SIZE=100;

export function DataPreparationStudio({datasetId,datasets,onSelect}:{datasetId:string;datasets:DatasetSummary[];onSelect:(id:string)=>void}){
 const qc=useQueryClient();
 const [page,setPage]=useState(0);
 const [rows,setRows]=useState<Record<string,unknown>[]>([]);
 const [selected,setSelected]=useState<{row:number;column:string}|null>(null);
 const [nulls,setNulls]=useState("-999.25, -999, -9999, -99999, 999.25, 9999");
 const [zeroCols,setZeroCols]=useState(""); const [depth,setDepth]=useState("");
 const [scaling,setScaling]=useState<"none"|"standard"|"minmax"|"robust">("none");
 const [scaleCols,setScaleCols]=useState(""); const [despike,setDespike]=useState(true);
 const [smooth,setSmooth]=useState(false); const [clip,setClip]=useState(false);
 const [ops,setOps]=useState<Array<Record<string,unknown>>>([]);
 const [rename,setRename]=useState<{column:string;name:string}|null>(null);
 const [newColumn,setNewColumn]=useState(""); const [formula,setFormula]=useState("");

 const offset=page*PAGE_SIZE;
 const preview=useQuery({
   queryKey:["prep-preview",datasetId,page],
   queryFn:()=>fetchDatasetPreview(datasetId,offset,PAGE_SIZE),
   enabled:Boolean(datasetId),
   staleTime:30000
 });
 const quality=useQuery({queryKey:["prep-quality",datasetId],queryFn:()=>fetchDatasetQuality(datasetId),enabled:Boolean(datasetId),staleTime:60000});

 useEffect(()=>{setPage(0);setOps([]);setSelected(null)},[datasetId]);
 useEffect(()=>{setRows(preview.data?.rows.map(row=>({...row}))??[])},[preview.data]);

 const columns=preview.data?.columns??[];
 const totalRows=preview.data?.total_rows??0;
 const totalPages=Math.max(1,Math.ceil(totalRows/PAGE_SIZE));
 const current=datasets.find(d=>d.dataset_id===datasetId);
 const pageStart=totalRows===0?0:offset+1;
 const pageEnd=Math.min(offset+rows.length,totalRows);

 const save=useMutation({
   mutationFn:()=>editDataset(datasetId,{name:`${current?.name??"Dataset"} · edited`,operations:ops}),
   onSuccess:async dataset=>{await qc.invalidateQueries({queryKey:["platform","datasets"]});onSelect(dataset.dataset_id)}
 });
 const prepare=useMutation({
   mutationFn:()=>prepareDataset(datasetId,{
     name:`${current?.name??"Dataset"} · ML-ready`,
     null_values:nulls.split(",").map(Number).filter(Number.isFinite),
     zero_as_null_columns:zeroCols.split(",").map(x=>x.trim()).filter(Boolean),
     depth_column:depth||null,interpolate_limit:3,despike,smooth,
     clip_physical_ranges:clip,scaling,
     scaling_columns:scaleCols.split(",").map(x=>x.trim()).filter(Boolean)
   }),
   onSuccess:async dataset=>{await qc.invalidateQueries({queryKey:["platform","datasets"]});onSelect(dataset.dataset_id)}
 });

 function absoluteRow(localRow:number){return offset+localRow}
 function setCell(localRow:number,column:string,value:string){
   setRows(items=>items.map((row,index)=>index===localRow?{...row,[column]:value}:row));
   setOps(items=>[...items,{action:"set_cell",row:absoluteRow(localRow),column,value}]);
 }
 async function paste(){if(!selected)return;const value=await navigator.clipboard.readText();setCell(selected.row,selected.column,value)}
 async function copy(){if(!selected)return;await navigator.clipboard.writeText(String(rows[selected.row]?.[selected.column]??""))}

 return <Stack spacing={2}>
  <Paper variant="outlined" sx={{p:2}}>
   <Grid container spacing={2} alignItems="center">
    <Grid item xs={12} md={5}><FormControl fullWidth><InputLabel>Dataset to inspect</InputLabel><Select label="Dataset to inspect" value={datasetId} onChange={event=>onSelect(event.target.value)}>{datasets.map(dataset=><MenuItem key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name} · {dataset.row_count??0} rows</MenuItem>)}</Select></FormControl></Grid>
    <Grid item xs={12} md={7}><Stack direction="row" gap={1} flexWrap="wrap"><Button startIcon={<Clipboard size={15}/>} onClick={copy} disabled={!selected}>Copy</Button><Button startIcon={<Clipboard size={15}/>} onClick={paste} disabled={!selected}>Paste</Button><Button startIcon={<Plus size={15}/>} onClick={()=>setNewColumn("new_column")}>Add column</Button><Button startIcon={<Plus size={15}/>} onClick={()=>{setRows(items=>[...items,{}]);setOps(items=>[...items,{action:"add_row",values:{}}])}}>Add row</Button><Button startIcon={<Save size={15}/>} variant="contained" onClick={()=>save.mutate()} disabled={!ops.length||save.isPending}>Save edited copy</Button><Button startIcon={<Download size={15}/>} onClick={()=>current&&downloadDatasetFile(datasetId,current.file_name)}>Download CSV</Button></Stack></Grid>
   </Grid>
  </Paper>

  {(quality.data?.unit_warnings.length??0)>0&&<Alert severity="warning"><b>Unit review:</b> missing units are flagged but do not block the workflow.<Stack mt={1}>{quality.data!.unit_warnings.map(warning=><span key={warning}>• {warning}</span>)}</Stack></Alert>}
  {(quality.data?.warnings.length??0)>0&&<Alert severity="info">{quality.data!.warnings.join(" ")}</Alert>}

  <Grid container spacing={2}>
   <Grid item xs={12} lg={8}>
    <Paper variant="outlined">
     <Stack direction={{xs:"column",sm:"row"}} justifyContent="space-between" alignItems={{xs:"flex-start",sm:"center"}} gap={1} p={1.5}>
      <Typography variant="body2">Rows {pageStart.toLocaleString()}–{pageEnd.toLocaleString()} of {totalRows.toLocaleString()}</Typography>
      <Stack direction="row" alignItems="center" gap={1}>
       <Button size="small" startIcon={<ChevronLeft size={15}/>} disabled={page===0||preview.isFetching} onClick={()=>setPage(value=>Math.max(0,value-1))}>Previous</Button>
       <Typography variant="caption">Page {page+1} of {totalPages}</Typography>
       <Button size="small" endIcon={<ChevronRight size={15}/>} disabled={page>=totalPages-1||preview.isFetching} onClick={()=>setPage(value=>Math.min(totalPages-1,value+1))}>Next</Button>
      </Stack>
     </Stack>
     <TableContainer sx={{maxHeight:520}}><Table stickyHeader size="small">
      <TableHead><TableRow><TableCell>#</TableCell>{columns.map(column=><TableCell key={column} sx={{minWidth:145,fontWeight:800}}><Stack direction="row" alignItems="center">{column}<Tooltip title="Rename"><Button size="small" onClick={()=>setRename({column,name:column})}>✎</Button></Tooltip><Tooltip title="Delete column"><Button color="error" variant="text" size="small" sx={{opacity:.55,minWidth:30}} onClick={()=>setOps(items=>[...items,{action:"delete_column",column}])}><Trash2 size={13}/></Button></Tooltip></Stack></TableCell>)}</TableRow></TableHead>
      <TableBody>{rows.map((row,index)=><TableRow key={`${offset}-${index}`} hover selected={selected?.row===index}><TableCell><Button color="error" variant="text" size="small" sx={{opacity:.5,minWidth:28}} onClick={()=>{setRows(items=>items.filter((_,rowIndex)=>rowIndex!==index));setOps(items=>[...items,{action:"delete_row",row:absoluteRow(index)}])}}><Trash2 size={13}/></Button>{absoluteRow(index)+1}</TableCell>{columns.map(column=><TableCell key={column} onClick={()=>setSelected({row:index,column})}><TextField variant="standard" value={row[column]??""} onChange={event=>setCell(index,column,event.target.value)} fullWidth/></TableCell>)}</TableRow>)}</TableBody>
     </Table></TableContainer>
     <Typography variant="caption" color="text.secondary" display="block" p={1.5}>The full dataset is available page by page. Only {PAGE_SIZE} rows are held in browser memory at a time. Edits use absolute row numbers and are applied when you save a new lineage-tracked copy.</Typography>
    </Paper>
   </Grid>

   <Grid item xs={12} lg={4}><Paper variant="outlined" sx={{p:2}}><Stack spacing={1.5}><Typography variant="h6">Petroleum ML preparation</Typography><TextField label="Null markers" value={nulls} onChange={event=>setNulls(event.target.value)} helperText="0 is never treated as null globally."/><TextField label="Columns where zero means missing" value={zeroCols} onChange={event=>setZeroCols(event.target.value)} helperText="Optional, comma-separated."/><TextField select label="Depth/time column" value={depth} onChange={event=>setDepth(event.target.value)}><MenuItem value="">Auto-detect</MenuItem>{columns.map(column=><MenuItem key={column} value={column}>{column}</MenuItem>)}</TextField><FormControl><InputLabel>Scaling</InputLabel><Select label="Scaling" value={scaling} onChange={event=>setScaling(event.target.value as typeof scaling)}><MenuItem value="none">None / model-aware pipeline</MenuItem><MenuItem value="standard">Standardisation</MenuItem><MenuItem value="minmax">Min-max normalisation</MenuItem><MenuItem value="robust">Robust scaling</MenuItem></Select></FormControl><TextField label="Columns to scale" value={scaleCols} onChange={event=>setScaleCols(event.target.value)} helperText="Blank means all numeric logs except depth."/><FormControlLabel control={<Checkbox checked={despike} onChange={event=>setDespike(event.target.checked)}/>} label="Hampel despiking"/><FormControlLabel control={<Checkbox checked={smooth} onChange={event=>setSmooth(event.target.checked)}/>} label="Optional smoothing"/><FormControlLabel control={<Checkbox checked={clip} onChange={event=>setClip(event.target.checked)}/>} label="Clip to physical ranges"/><Button variant="contained" startIcon={<ShieldCheck/>} onClick={()=>prepare.mutate()} disabled={prepare.isPending}>{prepare.isPending?"Preparing…":"Create ML-ready dataset"}</Button>{prepare.isError&&<Alert severity="error">{prepare.error instanceof Error?prepare.error.message:"Preparation failed"}</Alert>}<Alert severity="success">Units are warning-only. Training continues when units are absent.</Alert></Stack></Paper></Grid>
  </Grid>

  <Dialog open={Boolean(rename)} onClose={()=>setRename(null)}><DialogTitle>Rename column</DialogTitle><DialogContent><TextField autoFocus margin="dense" value={rename?.name??""} onChange={event=>setRename(value=>value?{...value,name:event.target.value}:value)}/></DialogContent><DialogActions><Button onClick={()=>setRename(null)}>Cancel</Button><Button onClick={()=>{if(rename){setOps(items=>[...items,{action:"rename_column",column:rename.column,new_name:rename.name}]);setRename(null)}}}>Apply</Button></DialogActions></Dialog>
  <Dialog open={Boolean(newColumn)} onClose={()=>setNewColumn("")}><DialogTitle>Add derived column</DialogTitle><DialogContent><Stack spacing={2} mt={1}><TextField label="Column name" value={newColumn} onChange={event=>setNewColumn(event.target.value)}/><TextField label="Formula or leave blank" value={formula} onChange={event=>setFormula(event.target.value)} helperText="Example: 0.5 * (NPHI + PHID)"/></Stack></DialogContent><DialogActions><Button onClick={()=>setNewColumn("")}>Cancel</Button><Button onClick={()=>{setOps(items=>[...items,formula?{action:"formula_column",column:newColumn,expression:formula}:{action:"add_column",column:newColumn,default_value:null}]);setNewColumn("");setFormula("")}}>Add</Button></DialogActions></Dialog>
 </Stack>
}
