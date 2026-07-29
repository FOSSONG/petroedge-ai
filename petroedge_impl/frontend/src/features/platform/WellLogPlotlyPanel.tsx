import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { Download } from "lucide-react";
import PlotlyModule from "plotly.js-dist-min";
import { downloadV1Report, fetchDatasets, fetchInterpretation } from "./platformApi";

const Plotly = ((PlotlyModule as unknown as { default?: unknown }).default ?? PlotlyModule) as {
  react: (element: HTMLDivElement, data: unknown[], layout: object, config: object) => Promise<void>;
  purge: (element: HTMLDivElement) => void;
  Plots?: { resize: (element: HTMLDivElement) => void };
};

type PlotlyChartProps = {
  data: unknown[];
  layout: object;
  config: object;
};

function PlotlyChart({ data, layout, config }: PlotlyChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [plotError, setPlotError] = useState<string | null>(null);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    let active = true;
    setPlotError(null);

    void Plotly.react(element, data, layout, config).catch((error: unknown) => {
      if (active) {
        setPlotError(error instanceof Error ? error.message : "Unable to render the interactive log plot.");
      }
    });

    const handleResize = () => {
      if (containerRef.current && Plotly.Plots?.resize) {
        Plotly.Plots.resize(containerRef.current);
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      active = false;
      window.removeEventListener("resize", handleResize);
      if (element) Plotly.purge(element);
    };
  }, [data, layout, config]);

  if (plotError) return <Alert severity="error">Plot rendering failed: {plotError}</Alert>;
  return <Box ref={containerRef} sx={{ width: "100%", minHeight: 720 }} />;
}

const asFiniteNumber = (value: unknown): number | null => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

function robustRange(values: Array<number | null>, fallback: [number, number], clamp?: [number, number]): [number, number] {
  const valid = values.filter((value): value is number => value !== null && Number.isFinite(value)).sort((a, b) => a - b);
  if (valid.length < 2) return fallback;
  const at = (fraction: number) => valid[Math.min(valid.length - 1, Math.max(0, Math.floor((valid.length - 1) * fraction)))];
  let low = at(0.02);
  let high = at(0.98);
  if (low === high) {
    const pad = Math.max(Math.abs(low) * 0.1, 0.05);
    low -= pad; high += pad;
  } else {
    const pad = (high - low) * 0.08;
    low -= pad; high += pad;
  }
  if (clamp) { low = Math.max(clamp[0], low); high = Math.min(clamp[1], high); }
  return [low, high];
}

export function WellLogPlotlyPanel() {
  const datasets = useQuery({
    queryKey: ["platform", "datasets"],
    queryFn: fetchDatasets,
  });
  const [chosen, setChosen] = useState("");
  const datasetId = chosen || datasets.data?.[0]?.dataset_id || "";

  const interpretation = useQuery({
    queryKey: ["v1", "interpretation", datasetId],
    queryFn: () => fetchInterpretation(datasetId),
    enabled: Boolean(datasetId),
  });

  const plot = useMemo(() => {
    const samples = interpretation.data?.samples ?? [];
    const validSamples = samples.filter((sample) => asFiniteNumber(sample.depth) !== null);
    const depth = validSamples.map((sample) => asFiniteNumber(sample.depth));
    const intervals = (interpretation.data?.intervals ?? [])
      .map((interval) => ({
        topDepth: asFiniteNumber(interval.top_depth),
        baseDepth: asFiniteNumber(interval.base_depth),
        samples: asFiniteNumber(interval.samples),
      }))
      .filter(
        (interval): interval is { topDepth: number; baseDepth: number; samples: number | null } =>
          interval.topDepth !== null && interval.baseDepth !== null,
      );

    const track = (field: string, name: string, unit: string, xaxis: string) => ({
      x: validSamples.map((sample) => asFiniteNumber((sample as Record<string, unknown>)[field])),
      y: depth,
      name: `${name} (${unit})`,
      xaxis,
      yaxis: "y",
      type: "scatter",
      mode: "lines",
      connectgaps: false,
      hovertemplate: `${name}: %{x} ${unit}<br>Depth: %{y} m<extra></extra>`,
    });

    const traces = [
      track("gr", "GR", "API", "x"),
      track("rt", "RT", "Ω·m", "x2"),
      track("rhob", "RHOB", "g/cm³", "x3"),
      track("nphi", "NPHI", "v/v", "x4"),
      track("porosity", "PHI", "v/v", "x5"),
      track("water_saturation", "SW", "v/v", "x6"),
      track("hydrocarbon_probability", "HC PROB", "fraction", "x7"),
    ];

    const domains: Array<[number, number]> = [
      [0.00, 0.12],
      [0.145, 0.265],
      [0.29, 0.41],
      [0.435, 0.555],
      [0.58, 0.70],
      [0.725, 0.845],
      [0.87, 0.99],
    ];

    const axis = (
      title: string,
      unit: string,
      domain: [number, number],
      extra: Record<string, unknown> = {},
    ) => ({
      title: { text: `<b>${title}</b><br><span style="font-size:10px">${unit}</span>`, font: { size: 12 } },
      domain,
      anchor: "y",
      side: "top",
      showgrid: true,
      zeroline: false,
      fixedrange: false,
      ticks: "outside",
      tickfont: { size: 9 },
      titlefont: { size: 12 },
      ...extra,
    });

    const valuesFor = (field: string) => validSamples.map((sample) => asFiniteNumber((sample as Record<string, unknown>)[field]));
    const grRange = robustRange(valuesFor("gr"), [0, 150], [0, 300]);
    const rtValues = valuesFor("rt").filter((value): value is number => value !== null && value > 0);
    const rtLinear = robustRange(rtValues, [0.2, 2000], [0.01, 100000]);
    const rtRange: [number, number] = [Math.log10(rtLinear[0]), Math.log10(rtLinear[1])];
    const rhobRange = robustRange(valuesFor("rhob"), [1.95, 2.95], [1, 3.5]);
    const nphiRange = robustRange(valuesFor("nphi"), [-0.15, 0.45], [-0.3, 0.8]);
    const phiRange = robustRange(valuesFor("porosity"), [0, 0.4], [-0.05, 0.65]);
    const swRange = robustRange(valuesFor("water_saturation"), [0, 1], [0, 1]);
    const hcRange = robustRange(valuesFor("hydrocarbon_probability"), [0, 1], [0, 1]);

    const shapes = intervals.map((interval) => ({
      type: "rect",
      xref: "paper",
      x0: 0,
      x1: 1,
      yref: "y",
      y0: interval.topDepth,
      y1: interval.baseDepth,
      fillcolor: "rgba(16, 185, 129, 0.12)",
      line: { width: 0 },
      layer: "below",
    }));

    const layout = {
      height: 760,
      autosize: true,
      showlegend: false,
      margin: { l: 72, r: 20, t: 118, b: 28 },
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      hovermode: "y unified",
      dragmode: "zoom",
      title: { text: "PetroEdge multitrack well-log interpretation", x: 0.5, xanchor: "center", y: 0.99 },
      shapes,
      yaxis: {
        autorange: "reversed",
        title: { text: "Depth (m)", font: { size: 12 } },
        domain: [0, 0.91],
        showgrid: true,
        gridcolor: "#e5e7eb",
      },
      xaxis: axis("GR", "API", domains[0], { range: grRange }),
      xaxis2: axis("RT", "Ω·m", domains[1], { type: "log", range: rtRange }),
      xaxis3: axis("RHOB", "g/cm³", domains[2], { range: rhobRange }),
      xaxis4: axis("NPHI", "v/v", domains[3], { range: [nphiRange[1], nphiRange[0]] }),
      xaxis5: axis("PHI", "v/v", domains[4], { range: phiRange }),
      xaxis6: axis("SW", "v/v", domains[5], { range: swRange }),
      xaxis7: axis("HC PROB", "fraction", domains[6], { range: hcRange }),
    };

    return { traces, layout, sampleCount: validSamples.length, intervals };
  }, [interpretation.data]);

  const config = useMemo(
    () => ({ responsive: true, displaylogo: false, scrollZoom: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] }),
    [],
  );

  if (datasets.isLoading) {
    return <Stack alignItems="center" py={8}><CircularProgress /></Stack>;
  }

  return (
    <Stack spacing={2.5}>
      <Paper className="hero-panel" sx={{ p: 3 }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
          <Box>
            <Chip label="Plotly interactive viewer" className="hero-chip" />
            <Typography variant="h4" fontWeight={850} mt={1}>Interactive Logs & AI Interpretation</Typography>
            <Typography sx={{ mt: 1, color: "#ffffff !important", opacity: 1 }}>
              Measured curves and AI-derived properties share a synchronised depth axis with zoom, pan and hover inspection.
            </Typography>
          </Box>
          <Stack minWidth={{ md: 320 }} gap={1}>
            <FormControl fullWidth variant="outlined" sx={{ minWidth: { xs: 260, md: 360 }, bgcolor: "white", borderRadius: 1 }}>
              <InputLabel id="interactive-logs-dataset-label" shrink sx={{ bgcolor: "white", px: 0.5, color: "#073b42", fontWeight: 700 }}>
                Dataset
              </InputLabel>
              <Select
                labelId="interactive-logs-dataset-label"
                id="interactive-logs-dataset"
                label="Dataset"
                notched
                value={datasetId}
                onChange={(event) => setChosen(event.target.value)}
                sx={{ minHeight: 56, color: "#073b42", fontWeight: 650 }}
              >
                {(datasets.data ?? []).map((dataset) => (
                  <MenuItem value={dataset.dataset_id} key={dataset.dataset_id}>{dataset.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Button
              variant="contained"
              startIcon={<Download size={17} />}
              onClick={() => downloadV1Report(datasetId)}
              disabled={!datasetId}
              sx={{ bgcolor: "white", color: "#073b42", "&:hover": { bgcolor: "#eefafa" } }}
            >
              Download interpretation PDF
            </Button>
          </Stack>
        </Stack>
      </Paper>

      {datasets.isError && (
        <Alert severity="error">{datasets.error instanceof Error ? datasets.error.message : "Unable to load datasets."}</Alert>
      )}

      {!datasetId && (
        <Alert severity="info">Upload a CSV, Parquet or LAS dataset before opening Interactive Logs.</Alert>
      )}

      {interpretation.isLoading && datasetId && (
        <Stack alignItems="center" py={6} gap={2}><CircularProgress /><Typography>Loading interpreted log tracks…</Typography></Stack>
      )}

      {interpretation.isError && (
        <Alert severity="error">
          {interpretation.error instanceof Error ? interpretation.error.message : "Interpretation failed."}
        </Alert>
      )}

      {interpretation.data && (
        <>
          <Stack direction="row" gap={1} flexWrap="wrap">
            {Object.entries(interpretation.data.summary ?? {}).slice(0, 8).map(([key, value]) => (
              <Chip key={key} label={`${key.replace(/_/g, " ")}: ${String(value)}`} />
            ))}
          </Stack>

          <Paper variant="outlined" sx={{ overflow: "hidden" }}>
            <Box sx={{ px: 2, py: 1.5, bgcolor: "#f0fdfa", borderBottom: "1px solid #d1fae5" }}>
              <Typography fontWeight={800}>Potential Pay Intervals</Typography>
              <Typography variant="body2" color="text.secondary">
                Depths are screening results from the Niger Delta-calibrated interpretation rules and require geological validation.
              </Typography>
            </Box>
            {plot.intervals.length === 0 ? (
              <Alert severity="info" sx={{ borderRadius: 0 }}>No potential pay interval was identified in the interpreted depth range.</Alert>
            ) : (
              <Table size="small" aria-label="Potential pay interval depths">
                <TableHead>
                  <TableRow>
                    <TableCell>Interval</TableCell>
                    <TableCell align="right">Top depth (m)</TableCell>
                    <TableCell align="right">Base depth (m)</TableCell>
                    <TableCell align="right">Gross thickness (m)</TableCell>
                    <TableCell align="right">Pay samples</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {plot.intervals.map((interval, index) => (
                    <TableRow key={`${interval.topDepth}-${interval.baseDepth}-${index}`} hover>
                      <TableCell component="th" scope="row" sx={{ fontWeight: 750 }}>Pay {index + 1}</TableCell>
                      <TableCell align="right">{interval.topDepth.toFixed(2)}</TableCell>
                      <TableCell align="right">{interval.baseDepth.toFixed(2)}</TableCell>
                      <TableCell align="right">{Math.abs(interval.baseDepth - interval.topDepth).toFixed(2)}</TableCell>
                      <TableCell align="right">{interval.samples ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Paper>

          {plot.sampleCount === 0 ? (
            <Alert severity="warning">The selected dataset contains no valid depth-linked samples for plotting.</Alert>
          ) : (
            <Paper variant="outlined" sx={{ p: 1.5, overflow: "hidden" }}>
              <PlotlyChart data={plot.traces} layout={plot.layout} config={config} />
            </Paper>
          )}
        </>
      )}
    </Stack>
  );
}
