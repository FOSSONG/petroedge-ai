import {downloadTable} from "./downloadTable";
import {useState} from "react";
import {useMutation} from "@tanstack/react-query";
import {Alert,Button,Paper,Stack,TextField,Typography} from "@mui/material";
import {apiRequest} from "../../api/http";
export function MeasuredEvidencePanel({id}:{id:string}){
 const [q,setQ]=useState("Summarise data quality and missing curves");
 const run=useMutation({mutationFn:()=>apiRequest<{answer:string;evidence:string[];limitations:string[]}>(`/datasets/${id}/measured-evidence`,{method:"POST",body:JSON.stringify({question:q})})});
 return <Paper variant="outlined" sx={{p:2}}><Stack spacing={1}><Typography variant="h6">Measured-data evidence assistant</Typography><Typography>Reads measured curves or retrieves cited passages from a selected searchable PDF. Answers include the source checksum. PDF retrieval fits a text index; it does not train a language model.</Typography><TextField label="Question about measured data" value={q} onChange={e=>{setQ(e.target.value);run.reset()}}/><Button disabled={!id||q.trim().length<2||run.isPending} onClick={()=>run.mutate()}>Review measured evidence</Button>{run.isError&&<Alert severity="error">{run.error.message}</Alert>}{run.data&&<><Typography sx={{whiteSpace:"pre-wrap"}}>{run.data.answer}</Typography><Button onClick={()=>downloadTable("petroedge-evidence.csv",[{question:q,answer:run.data!.answer,evidence:run.data!.evidence.join("; "),limitations:run.data!.limitations.join("; ")}])}>Download evidence CSV</Button>{run.data.evidence.map(x=><Typography key={x} variant="caption" sx={{overflowWrap:"anywhere"}}>{x}</Typography>)}{run.data.limitations.map(x=><Typography key={x} variant="caption">{x}</Typography>)}</>}</Stack></Paper>;
}
