import { downloadReport } from "../platform/platformApi";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Accordion, AccordionSummary, AccordionDetails, Alert, Button, Stack, TextField, Typography } from "@mui/material";
import { apiRequest } from "../../api/http";
const labels:Record<string,string>={porosity:"Porosity (v/v)",permeability_md:"Permeability (mD)",water_saturation:"Water saturation (v/v)",hydrocarbon_probability:"Hydrocarbon score",input:"Source measurements",explanation:"Methods and model details",provenance:"Source provenance"};
const label=(key:string)=>labels[key]??key.replace(/_/g," ");
function Details({value}:{value:unknown}){
 if(value===null||value===undefined)return <Typography component="span">Not available</Typography>;
 if(typeof value!=="object")return <Typography component="span" sx={{overflowWrap:"anywhere"}}>{typeof value==="number"?Number(value.toPrecision(6)).toLocaleString():String(value)}</Typography>;
 return <Stack spacing={1}>{Object.entries(value).map(([key,item])=><div key={key}>{item!==null&&typeof item==="object"?<Accordion><AccordionSummary>{label(key)}</AccordionSummary><AccordionDetails><Details value={item}/></AccordionDetails></Accordion>:<Typography component="div"><strong>{label(key)}: </strong><Details value={key==="lithology"&&/^[0-9]+$/.test(String(item))?"Unmapped lithology class "+item:item}/></Typography>}</div>)}</Stack>;
}
type Saved = { analysis_id: string; provenance: { well_id: string; source_row: number; analyzed_at: string } };
export function SavedAnalysesPanel() {
  const [selected, setSelected] = useState("");
  const [question, setQuestion] = useState("Summarise this result");
  const evidence = useMutation({ mutationFn: () => apiRequest<{ answer: string; facts: unknown; citations: { analysis_id: string; path: string }[]; limitation: string }>(`/analytics/saved/${encodeURIComponent(selected)}/assistant`, { method: "POST", body: JSON.stringify({ question }) }) });
  const report = useMutation({ mutationFn: () => apiRequest<Record<string, unknown>>("/reports/generate", { method: "POST", body: JSON.stringify({ source_type: "saved_analysis", source_id: selected, formats: ["pdf", "xlsx"], include_alerts: false }) }) });
  const download = useMutation({mutationFn:(format:string) => downloadReport(String(report.data?.report_id),format)});
  const records = useQuery({ queryKey: ["saved-analyses"], queryFn: () => apiRequest<Saved[]>("/analytics/saved") });
  const result = useQuery({ queryKey: ["saved-analysis", selected], queryFn: () => apiRequest<Record<string, unknown>>(`/analytics/saved/${encodeURIComponent(selected)}`), enabled: Boolean(selected) });
  return <Stack spacing={2}>
    <Typography variant="h6">Saved analyses</Typography>
    <Button onClick={() => { void records.refetch(); if(selected)void result.refetch(); }}>Refresh saved analyses</Button>
    {records.data?.length === 0 && <Typography>No saved analyses yet.</Typography>}
    {records.data?.map(r => <Button key={r.analysis_id} onClick={() => { setSelected(r.analysis_id); evidence.reset(); report.reset(); download.reset(); }}>{r.provenance.well_id} | row {r.provenance.source_row} | {r.provenance.analyzed_at}</Button>)}
    {(records.isError || result.isError) && <Alert severity="error">Saved analysis could not be loaded.</Alert>}
    {selected && <Stack spacing={1}>
      <TextField label="Ask about this saved analysis" value={question} onChange={e => setQuestion(e.target.value)} />
      <Button disabled={question.trim().length < 3 || evidence.isPending} onClick={() => evidence.mutate()}>Look up saved evidence</Button>
      <Button disabled={report.isPending} onClick={() => report.mutate()}>Create saved-analysis report</Button>
    </Stack>}
    {(evidence.isError || report.isError) && <Alert severity="error">{String(evidence.error?.message ?? report.error?.message)}</Alert>}
    {evidence.data && <Stack><Typography>{evidence.data.answer}</Typography><Alert severity="info">{evidence.data.limitation}</Alert><Details value={evidence.data.facts}/>{evidence.data.citations.map(c => <Typography key={c.path}>Source: {c.analysis_id} | {c.path}</Typography>)}</Stack>}
    {report.data && <Alert severity="success">Report created: {String(report.data.report_id ?? "available in Reports")}. Use the download buttons below.</Alert>}
    {report.data?.report_id != null && <Stack direction="row" spacing={1}>{["pdf","xlsx"].map(format=><Button key={format} disabled={download.isPending} onClick={()=>download.mutate(format)}>Download {format.toUpperCase()} report</Button>)}</Stack>}
    {download.isError && <Alert severity="error">{download.error.message}</Alert>}
    {result.data && <Stack spacing={2}><Typography variant="h6">Analysis results</Typography><Details value={result.data}/></Stack>}
  </Stack>;
}
