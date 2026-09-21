import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { apiRequest } from "../../api/http";
import { fetchDatasets } from "../platform/platformApi";
type Choice = { source: string; unit: string; null_values: number[] };
export function WellDatasetBindingPanel({ wellId }: { wellId: string }) {
  const [datasetId, setDatasetId] = useState("");
  const [curves, setCurves] = useState<Record<string, Choice>>({});
  const [reference, setReference] = useState("MD");
  const [nullText, setNullText] = useState("");
  const cache = useQueryClient();
  const datasets = useQuery({ queryKey: ["platform", "datasets"], queryFn: fetchDatasets });
  const config = useQuery({ queryKey: ["well", wellId, "binding"], queryFn: () => apiRequest<{ binding: unknown; supported_units: Record<string, Record<string, number>> }>(`/wells/${encodeURIComponent(wellId)}/log-dataset`) });
  const eligible = (datasets.data ?? []).filter(d => d.well_name === wellId && ["well_log", "processed_well_log"].includes(d.dataset_type));
  const dataset = eligible.find(d => d.dataset_id === datasetId);
  const bind = useMutation({
    mutationFn: () => {
      const codes = nullText.trim() ? nullText.split(",").map(x => Number(x.trim())) : [];
      if (codes.some(x => !Number.isFinite(x))) throw new Error("Null codes must be comma-separated numbers.");
      const choices = Object.fromEntries(Object.entries(curves).filter(([, c]) => c.source).map(([k, c]) => [k, { ...c, null_values: codes }]));
      return apiRequest(`/wells/${encodeURIComponent(wellId)}/log-dataset`, { method: "PUT", body: JSON.stringify({ dataset_id: datasetId, mapping: { version: 1, depth_reference: reference, curves: choices } }) });
    },
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ["well", wellId] }); },
  });
  return <Stack spacing={2}>
    <Alert severity="info">Select source curves and declare their units. Names do not establish units. Original uploads remain unchanged. Analysis requires every listed curve, valid values and measured depth (MD).</Alert>
    <TextField select label="Uploaded log dataset" value={dataset?.dataset_id ?? ""} onChange={e => { setDatasetId(e.target.value); setCurves({}); bind.reset(); }}>
      {eligible.map(d => <MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}
    </TextField>
    <TextField select label="Depth reference" value={reference} onChange={e => setReference(e.target.value)}>{["MD", "TVD", "TVDSS"].map(r => <MenuItem key={r} value={r}>{r}</MenuItem>)}</TextField>
    {dataset && Object.entries(config.data?.supported_units ?? {}).map(([target, units]) => <Stack key={target} direction="row" spacing={1}>
      <TextField fullWidth select label={target} value={curves[target]?.source ?? ""} onChange={e => setCurves({ ...curves, [target]: { source: e.target.value, unit: "", null_values: [] } })}>
        <MenuItem value="">Not mapped</MenuItem>{dataset.columns.map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
      </TextField>
      <TextField fullWidth select label="Source unit" value={curves[target]?.unit ?? ""} onChange={e => setCurves({ ...curves, [target]: { source: curves[target]?.source ?? "", unit: e.target.value, null_values: [] } })}>
        {Object.keys(units).map(u => <MenuItem key={u} value={u}>{u}</MenuItem>)}
      </TextField>
    </Stack>)}
    <TextField label="Declared null codes (comma-separated, optional)" value={nullText} onChange={e => setNullText(e.target.value)} />
    <Button disabled={!dataset || !curves.depth_m?.source || bind.isPending} onClick={() => bind.mutate()}>Save dataset and curve mapping</Button>
    {config.data?.binding != null && <Typography component="pre" sx={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(config.data.binding, null, 2)}</Typography>}
    {(datasets.isError || config.isError) && <Alert severity="error">Could not load mapping resources.</Alert>}
    {bind.isError && <Alert severity="error">{bind.error instanceof Error ? bind.error.message : "Mapping failed."}</Alert>}
    {bind.isSuccess && <Alert severity="success">Mapping saved. Log data refreshed.</Alert>}
  </Stack>;
}
