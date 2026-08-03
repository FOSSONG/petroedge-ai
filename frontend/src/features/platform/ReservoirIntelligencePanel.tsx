import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, CircularProgress, FormControl, Grid, InputLabel, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { Download, Droplets, RefreshCw, Waves } from "lucide-react";
import { SafePlot } from "../../components/SafePlot";
import { downloadV1Report, fetchDatasets, fetchInterpretation } from "./platformApi";

const number = (value: unknown): number | null => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; };
const percentage = (value: unknown) => `${((number(value) ?? 0) * 100).toFixed(1)}%`;
const label = (value: unknown) => String(value ?? "unknown").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

export function ReservoirIntelligencePanel() {
  const datasets = useQuery({ queryKey: ["platform", "datasets"], queryFn: fetchDatasets });
  const [chosen, setChosen] = useState("");
  const datasetId = chosen || datasets.data?.[0]?.dataset_id || "";
  const interpretation = useQuery({
    queryKey: ["v1", "interpretation", datasetId],
    queryFn: () => fetchInterpretation(datasetId),
    enabled: Boolean(datasetId),
    retry: 1,
  });

  const chart = useMemo(() => {
    const raw = Array.isArray(interpretation.data?.samples) ? interpretation.data.samples : [];
    const samples = raw.filter((sample) => number(sample.depth) !== null).slice(0, 5000);
    const depth = samples.map((sample) => number(sample.depth));
    const trace = (field: string, name: string, axis: string) => ({
      x: samples.map((sample) => number((sample as Record<string, unknown>)[field])), y: depth,
      type: "scatter", mode: "lines", name, xaxis: axis, yaxis: "y", connectgaps: false,
      hovertemplate: `${name}: %{x:.3f}<br>Depth: %{y:.2f} m<extra></extra>`,
    });
    const probability = (fluid: string, name: string) => ({
      x: samples.map((sample) => number((sample as Record<string, any>).fluid_probabilities?.[fluid]) !== null ? (number((sample as Record<string, any>).fluid_probabilities?.[fluid]) as number) * 100 : null),
      y: depth, type: "scatter", mode: "lines", name, xaxis: "x8", yaxis: "y", connectgaps: false,
      hovertemplate: `${name}: %{x:.1f}%<br>Depth: %{y:.2f} m<extra></extra>`,
    });
    const domains: Array<[number, number]> = [[0,.105],[.125,.23],[.25,.355],[.375,.48],[.50,.605],[.625,.73],[.75,.855],[.875,.995]];
    const axis = (title: string, domain: [number, number], extra: Record<string, unknown> = {}) => ({
      title: { text: title, font: { size: 11 } }, domain, anchor: "y", side: "top", showgrid: true, zeroline: false,
      tickformat: ".1f", fixedrange: false, ticks: "outside", tickfont: { size: 9 }, ...extra,
    });
    return {
      samples,
      data: [
        trace("gr", "GR", "x"), trace("rt", "RT", "x2"), trace("rhob", "RHOB", "x3"), trace("nphi", "NPHI", "x4"),
        trace("porosity", "Porosity", "x5"), trace("water_saturation", "Sw", "x6"), trace("hydrocarbon_probability", "HC probability", "x7"),
        probability("oil", "Oil"), probability("gas", "Gas"), probability("water", "Water"),
      ],
      layout: {
        height: 760, autosize: true, showlegend: true, legend: { orientation: "h", y: -0.08 }, margin: { l: 68, r: 20, t: 105, b: 70 },
        hovermode: "y unified", dragmode: "zoom", paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
        yaxis: { autorange: "reversed", title: { text: "Depth (m)" }, showgrid: true, tickformat: ".1f" },
        xaxis: axis("GR (API)", domains[0], { range: [0,150] }), xaxis2: axis("RT (Ω·m)", domains[1], { type: "log" }),
        xaxis3: axis("RHOB", domains[2]), xaxis4: axis("NPHI", domains[3], { autorange: "reversed" }),
        xaxis5: axis("PHI", domains[4]), xaxis6: axis("Sw", domains[5], { range: [0,1] }),
        xaxis7: axis("HC", domains[6], { range: [0,1] }), xaxis8: axis("Fluid probability (%)", domains[7], { range: [0,100] }),
      },
    };
  }, [interpretation.data]);

  const summary = interpretation.data?.summary ?? {};
  const fluidProbabilities = summary.fluid_probabilities && typeof summary.fluid_probabilities === "object"
    ? summary.fluid_probabilities as Record<string, unknown> : {};
  const intervals = Array.isArray(interpretation.data?.intervals) ? interpretation.data.intervals : [];

  const refresh = async () => {
    await Promise.all([
      datasets.refetch(),
      interpretation.refetch(),
    ]);
  };

  return <Stack spacing={3}>
    <Paper className="hero-panel" sx={{ p: { xs: 3, md: 4 } }}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
        <Box><Chip label="PetroEdge AI MVP" className="hero-chip"/><Typography variant="h4" mt={1.5}>Reservoir Intelligence</Typography><Typography mt={1}>Interactive petrophysical interpretation with explicit water, oil and gas screening.</Typography></Box>
        <Stack minWidth={{ md: 350 }} gap={1.25}>
          <FormControl sx={{ bgcolor: "background.paper", borderRadius: 1 }}><InputLabel>Dataset</InputLabel><Select label="Dataset" value={datasetId} onChange={(event) => setChosen(event.target.value)}>{(datasets.data ?? []).map((dataset) => <MenuItem key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name}</MenuItem>)}</Select></FormControl>
          <Stack direction="row" gap={1}><Button fullWidth variant="contained" startIcon={<RefreshCw size={16}/>} onClick={refresh}>Refresh</Button><Button fullWidth variant="contained" startIcon={<Download size={16}/>} disabled={!datasetId} onClick={() => downloadV1Report(datasetId)}>PDF</Button></Stack>
        </Stack>
      </Stack>
    </Paper>

    {(datasets.isLoading || interpretation.isLoading) && <Stack alignItems="center" py={5}><CircularProgress/><Typography mt={1} color="text.secondary">Loading reservoir interpretation…</Typography></Stack>}
    {datasets.isError && <Alert severity="error">{datasets.error instanceof Error ? datasets.error.message : "Unable to load datasets."}</Alert>}
    {!datasets.isLoading && !datasetId && <Alert severity="info">Upload a LAS, CSV or Parquet dataset to begin reservoir interpretation.</Alert>}
    {interpretation.isError && <Alert severity="error">{interpretation.error instanceof Error ? interpretation.error.message : "Reservoir interpretation failed."}</Alert>}

    {interpretation.data && <>
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><Paper variant="outlined" sx={{ p: 2.5, height: "100%" }}><Stack direction="row" gap={1} alignItems="center"><Droplets size={20}/><Typography variant="h6">Predominant fluid</Typography></Stack><Typography variant="h4" mt={2}>{label(summary.primary_fluid)}</Typography><Typography color="text.secondary">Confidence: {percentage(summary.fluid_confidence)}</Typography><Chip sx={{ mt: 2 }} label={label(summary.fluid_method ?? "log screening")} /></Paper></Grid>
        {(["oil","gas","water"] as const).map((fluid) => <Grid item xs={12} sm={4} md={8/3} key={fluid}><Paper variant="outlined" sx={{ p: 2.5, height: "100%" }}><Typography color="text.secondary">{label(fluid)} probability</Typography><Typography variant="h4" mt={1}>{percentage(fluidProbabilities[fluid])}</Typography></Paper></Grid>)}
      </Grid>

      <Alert severity="warning">Fluid typing is a screening interpretation. Confirm oil or gas using pressure gradients, formation testing, mud-gas, PVT, fluid sampling or production evidence.</Alert>

      {chart.samples.length > 0 ? <Paper variant="outlined" sx={{ p: 1.5, overflow: "hidden" }}><SafePlot data={chart.data} layout={chart.layout} minHeight={760}/></Paper> : <Alert severity="warning">No valid depth-linked samples were returned for plotting.</Alert>}

      <Paper variant="outlined" sx={{ overflow: "hidden" }}><Box sx={{ p: 2 }}><Typography variant="h6">Pay-interval summary</Typography></Box>{intervals.length === 0 ? <Alert severity="info" sx={{ borderRadius: 0 }}>No potential pay interval was identified.</Alert> : <Table size="small"><TableHead><TableRow><TableCell>Interval</TableCell><TableCell align="right">Top (m)</TableCell><TableCell align="right">Base (m)</TableCell><TableCell align="right">Thickness (m)</TableCell><TableCell align="right">Samples</TableCell></TableRow></TableHead><TableBody>{intervals.map((interval, index) => { const top=number(interval.top_depth)??0; const base=number(interval.base_depth)??0; return <TableRow key={`${top}-${base}-${index}`}><TableCell>Pay {index+1}</TableCell><TableCell align="right">{top.toFixed(1)}</TableCell><TableCell align="right">{base.toFixed(1)}</TableCell><TableCell align="right">{Math.abs(base-top).toFixed(1)}</TableCell><TableCell align="right">{String(interval.samples ?? "—")}</TableCell></TableRow>; })}</TableBody></Table>}</Paper>
    </>}
  </Stack>;
}
