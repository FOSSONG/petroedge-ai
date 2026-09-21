import { downloadReport } from "../platform/platformApi";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, Stack, TextField, Typography } from "@mui/material";
import { apiRequest } from "../../api/http";
type Saved = { analysis_id: string; provenance: { well_id: string; source_row: number; analyzed_at: string } };
export function SavedAnalysesPanel() {
  const [selected, setSelected] = useState("");
  const [question, setQuestion] = useState("Summarise this result");
  const evidence = useMutation({ mutationFn: () => apiRequest<{ answer: string; facts: unknown; citations: { analysis_id: string; path: string }[]; limitation: string }>(`/analytics/saved/${encodeURIComponent(selected)}/assistant`, { method: "POST", body: JSON.stringify({ question }) }) });
  const report = useMutation({ mutationFn: () => apiRequest<Record<string, unknown>>("/reports/generate", { method: "POST", body: JSON.stringify({ source_type: "saved_analysis", source_id: selected, formats: ["json", "html"], include_alerts: false }) }) });
  const download = useMutation({mutationFn:(format:string) => downloadReport(String(report.data?.report_id),format)});
  const records = useQuery({ queryKey: ["saved-analyses"], queryFn: () => apiRequest<Saved[]>("/analytics/saved") });
  const result = useQuery({ queryKey: ["saved-analysis", selected], queryFn: () => apiRequest<Record<string, unknown>>(`/analytics/saved/${encodeURIComponent(selected)}`), enabled: Boolean(selected) });
  return <Stack spacing={2}>
    <Typography variant="h6">Saved analyses</Typography>
    <Button onClick={() => { void records.refetch(); }}>Refresh saved analyses</Button>
    {records.data?.length === 0 && <Typography>No saved analyses yet.</Typography>}
    {records.data?.map(r => <Button key={r.analysis_id} onClick={() => { setSelected(r.analysis_id); evidence.reset(); report.reset(); }}>{r.provenance.well_id} ? row {r.provenance.source_row} ? {r.provenance.analyzed_at}</Button>)}
    {(records.isError || result.isError) && <Alert severity="error">Saved analysis could not be loaded.</Alert>}
    {selected && <Stack spacing={1}>
      <TextField label="Ask about this saved analysis" value={question} onChange={e => setQuestion(e.target.value)} />
      <Button disabled={question.trim().length < 3 || evidence.isPending} onClick={() => evidence.mutate()}>Look up saved evidence</Button>
      <Button disabled={report.isPending} onClick={() => report.mutate()}>Create saved-analysis report</Button>
    </Stack>}
    {(evidence.isError || report.isError) && <Alert severity="error">{String(evidence.error?.message ?? report.error?.message)}</Alert>}
    {evidence.data && <Stack><Typography>{evidence.data.answer}</Typography><Alert severity="info">{evidence.data.limitation}</Alert><Typography component="pre" sx={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(evidence.data.facts, null, 2)}</Typography>{evidence.data.citations.map(c => <Typography key={c.path}>Source: {c.analysis_id} ? {c.path}</Typography>)}</Stack>}
    {report.data && <Alert severity="success">Report created: {String(report.data.report_id ?? "available in Reports")}. Use the download buttons below.</Alert>}
    {report.data?.report_id != null && <Stack direction="row" spacing={1}>{["json","html"].map(format=><Button key={format} disabled={download.isPending} onClick={()=>download.mutate(format)}>Download {format.toUpperCase()} report</Button>)}</Stack>}
    {download.isError && <Alert severity="error">{download.error.message}</Alert>}
    {result.data && <Typography component="pre" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12 }}>{JSON.stringify(result.data, null, 2)}</Typography>}
  </Stack>;
}
