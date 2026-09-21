import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Chip, FormControl, InputLabel, MenuItem, Paper, Select, Stack, Typography } from "@mui/material";
import { fetchDatasets, fetchLasWizard, prepareDataset } from "./platformApi";
import { CurveMappingCopyPanel } from "./CurveMappingCopyPanel";
import { DataPreparationStudio } from "./DataPreparationStudio";

export function LasWizardPanel() {
  const client = useQueryClient();
  const datasets = useQuery({ queryKey: ["platform", "datasets"], queryFn: fetchDatasets });
  const [chosen, setChosen] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [mode, setMode] = useState("manual");
  const id = chosen || datasets.data?.[0]?.dataset_id || "";
  const q = useQuery({ queryKey: ["v1", "wizard", id], queryFn: () => fetchLasWizard(id), enabled: Boolean(id) });
  const auto = useMutation({
    mutationFn: () => prepareDataset(id, {
      name: `${datasets.data?.find(d => d.dataset_id === id)?.name ?? "Dataset"} - automatic QC copy`,
      null_values: [-999.25, -999, -9999, -99999], zero_as_null_columns: [],
      interpolate_limit: 0, despike: false, smooth: false, clip_physical_ranges: false,
      scaling: "none", scaling_columns: [],
    }),
    onSuccess: async data => { await client.invalidateQueries({ queryKey: ["platform", "datasets"] }); setChosen(data.dataset_id); },
  });
  return <Stack spacing={3}>
    <Typography variant="h4">LAS Wizard</Typography>
    <Typography>Inspect curve aliases, resolve source units, then prepare a separate dataset copy. Model training is available in the Training tab.</Typography>
    <Stack direction="row" spacing={2}>
      <FormControl fullWidth><InputLabel>Dataset</InputLabel><Select label="Dataset" value={id} disabled={auto.isPending} onChange={e => { setChosen(e.target.value); auto.reset(); }}>{(datasets.data ?? []).map(d => <MenuItem key={d.dataset_id} value={d.dataset_id}>{d.name}</MenuItem>)}</Select></FormControl>
      <Button disabled={q.isFetching || datasets.isFetching || auto.isPending} onClick={() => { void datasets.refetch(); if (id) void q.refetch(); }}>Refresh inspection</Button>
    </Stack>
    {(q.isLoading || datasets.isLoading) && <Alert severity="info">Inspecting dataset...</Alert>}
    {(q.isError || datasets.isError) && <Alert severity="error">{String(q.error?.message || datasets.error?.message)}</Alert>}
    {!id && !datasets.isLoading && <Alert severity="info">Upload a dataset in Datasets to begin.</Alert>}
    {q.data && <Paper variant="outlined" sx={{ p: 3 }}>
      <Typography variant="h6">Curve matching audit</Typography>
      <Typography>Matching identifies the curve quantity only. Units and measured/vertical depth must be reviewed separately. Ambiguous mnemonics require manual selection; unknown columns are retained.</Typography>
      <Stack direction="row" gap={1} flexWrap="wrap" mt={2}>{Object.entries(q.data.mnemonic_mapping).map(([source, target]) => <Chip key={source} color={target ? "success" : "warning"} label={`${source}: ${target ?? q.data.match_details?.[source]?.status ?? "unmatched"}`} title={JSON.stringify(q.data.match_details?.[source])}/>)}</Stack>
      <Typography mt={2}>Rows inspected: {q.data.qc.row_count} | Missing cells: {q.data.qc.missing_cells} | Duplicate rows: {q.data.qc.duplicate_rows}</Typography>
      <Alert severity="info" sx={{ mt: 2 }}>Curve coverage: {q.data.missing_recommended_curves.length ? `missing ${q.data.missing_recommended_curves.join(", ")}` : "all recommended curves detected"}. This is an inspection, not approval for training or interpretation.</Alert>
      {q.data.blocking_issues?.map((issue, i) => <Alert severity="warning" key={i} sx={{ mt: 1 }}>{issue}</Alert>)}
    </Paper>}
    {q.data && <CurveMappingCopyPanel key={id} id={id} mapping={q.data.mnemonic_mapping} declaredUnits={q.data.source_units??{}} onSelect={setChosen}/>}
    {id && <>
      <FormControl><InputLabel>Preparation mode</InputLabel><Select label="Preparation mode" value={mode} disabled={auto.isPending} onChange={e => setMode(e.target.value)}><MenuItem value="manual">Manual: inspect and adjust parameters</MenuItem><MenuItem value="automatic">Automatic: conservative QC copy</MenuItem></Select></FormControl>
      {mode === "automatic" ? <Paper variant="outlined" sx={{ p: 3 }}><Stack spacing={2}>
        <Typography>Automatic preparation replaces the listed negative null codes, recognises aliases and records QC and lineage in a new dataset. It preserves row order and duplicate depths. It does not infer units, fill gaps, scale features, smooth curves or create missing curves.</Typography>
        <Typography>Null markers: -999.25, -999, -9999, -99999. Use manual mode for other source conventions.</Typography>
        <Button variant="contained" disabled={auto.isPending || !q.data} onClick={() => auto.mutate()}>{auto.isPending ? "Preparing copy..." : "Run automatic preparation"}</Button>
        {auto.isError && <Alert severity="error">{auto.error.message}</Alert>}
        {auto.isSuccess && <Alert severity="success">A new QC copy was saved and selected. Review its units and QC before interpretation.</Alert>}
      </Stack></Paper> : <Stack spacing={2}><Typography variant="h6">Manual LAS preparation</Typography><Button onClick={()=>setEditorOpen(v=>!v)}>{editorOpen?"Close preparation editor":"Open preparation editor"}</Button>{editorOpen&&<DataPreparationStudio key={id} datasetId={id} datasets={datasets.data ?? []} onSelect={setChosen}/>}</Stack>}
      <Alert severity="info">For unknown mnemonics or source-unit conversion, use Well Logs / mapped well explorer to select each source curve, unit and depth reference explicitly.</Alert>
    </>}
  </Stack>;
}
