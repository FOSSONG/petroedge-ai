import { ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Slider,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import {
  Activity,
  Box as Cube,
  Database,
  Gauge,
  History,
  Pause,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { SafePlot } from "../../components/SafePlot";
import {
  fetchAssets,
  fetchDatasets,
  fetchReplay,
  fetchTwinHistory,
  fetchTwins,
  fetchTwinWorkspaceSummary,
  restoreTwinVersion,
  runTwinWorkspaceScenario,
  type DatasetSummary,
  type ReservoirTwin,
} from "./platformApi";

type ReplayEvent = {
  sequence: number;
  depth: number;
  logs: Record<string, number>;
  prediction: Record<string, string | number>;
  alerts: string[];
};

type TwinBinding = {
  datasetId: string;
  assetId: string;
  wellId: string;
  field: string;
};

const BINDINGS_KEY = "petroedge_digital_well_twin_bindings_v1";
const speeds = [
  { label: "0.5×", delay: 900 },
  { label: "1×", delay: 450 },
  { label: "2×", delay: 225 },
  { label: "5×", delay: 90 },
];

function readBindings(): Record<string, TwinBinding> {
  try {
    const value = JSON.parse(localStorage.getItem(BINDINGS_KEY) ?? "{}") as unknown;
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, TwinBinding>)
      : {};
  } catch {
    return {};
  }
}

function writeBinding(twinId: string, binding: TwinBinding): void {
  const bindings = readBindings();
  bindings[twinId] = binding;
  localStorage.setItem(BINDINGS_KEY, JSON.stringify(bindings));
}

function numberValue(value: unknown, fallback = 0): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function percent(value: unknown): string {
  return `${(numberValue(value) * 100).toFixed(1)}%`;
}


function eventState(event?: ReplayEvent): Record<string, string | number> {
  if (!event) return {};
  return {
    lithology: String(event.prediction.lithology ?? "Unknown"),
    porosity: numberValue(event.prediction.porosity),
    permeability: numberValue(
      event.prediction.permeability ?? event.prediction.permeability_md,
    ),
    water_saturation: numberValue(event.prediction.water_saturation),
    hydrocarbon_probability: numberValue(
      event.prediction.hydrocarbon_probability,
    ),
    pay_flag: String(event.prediction.pay_flag ?? "Non-pay"),
    anomaly_score: event.alerts.length > 0 ? 0.8 : 0.05,
    pressure: numberValue(event.logs.pressure, event.depth * 0.0105),
    temperature: numberValue(
      event.logs.temperature,
      25 + event.depth * 0.025,
    ),
    flow_rate: numberValue(event.logs.flow_rate),
  };
}

function propertyValue(event: ReplayEvent, property: string): number {
  if (property === "gamma_ray") return numberValue(event.logs.gr);
  return numberValue(eventState(event)[property]);
}

function display(value: unknown): string {
  if (typeof value === "number") {
    return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value ?? "—");
}

function numericPaths(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof item === "number" && Number.isFinite(item)) return [path];
    return item && typeof item === "object" && !Array.isArray(item)
      ? numericPaths(item, path)
      : [];
  });
}

function inferDatasetForTwin(
  twin: ReservoirTwin | undefined,
  datasets: DatasetSummary[],
): string {
  if (!twin) return "";
  const binding = readBindings()[twin.reservoir_id];
  if (binding?.datasetId) return binding.datasetId;
  const identity = `${twin.reservoir_id} ${twin.name}`.toLowerCase();
  return (
    datasets.find((dataset) => {
      const candidates = [
        dataset.name,
        dataset.well_name,
        dataset.reservoir_name,
      ]
        .filter(Boolean)
        .map((item) => String(item).toLowerCase());
      return candidates.some((candidate) => identity.includes(candidate));
    })?.dataset_id ?? ""
  );
}

function DynamicWell3D({
  events,
  index,
  property,
}: {
  events: ReplayEvent[];
  index: number;
  property: string;
}) {
  const visible = events.slice(0, Math.max(1, index + 1));
  const x = visible.map((_event, sample) => Math.sin(sample / 25) * 12);
  const y = visible.map((_event, sample) => Math.cos(sample / 31) * 8);
  const z = visible.map((event) => -event.depth);
  const values = visible.map((event) => propertyValue(event, property));

  const data = useMemo<unknown[]>(() => {
    const traces: unknown[] = [
      {
        type: "scatter3d",
        mode: "lines+markers",
        x,
        y,
        z,
        line: {
          width: 8,
          color: values,
          colorscale: "Viridis",
          colorbar: { title: property.replace(/_/g, " ") },
        },
        marker: {
          size: 5,
          color: values,
          colorscale: "Viridis",
          opacity: 0.72,
        },
        text: visible.map(
          (event) =>
            `Depth ${event.depth.toFixed(1)} m<br>${property.replace(/_/g, " ")}: ${propertyValue(event, property).toFixed(3)}<br>${String(event.prediction.lithology ?? "Unknown")}`,
        ),
        hovertemplate: "%{text}<extra></extra>",
        name: "Well state",
      },
    ];

    if (visible.length > 0) {
      traces.push({
        type: "scatter3d",
        mode: "markers",
        x: [x[x.length - 1]],
        y: [y[y.length - 1]],
        z: [z[z.length - 1]],
        marker: {
          size: 13,
          symbol: "diamond",
          color: "#ffffff",
          line: { width: 4, color: "#ff9800" },
        },
        text: [`Live depth ${visible[visible.length - 1].depth.toFixed(1)} m`],
        hovertemplate: "%{text}<extra></extra>",
        name: "Live depth",
      });
    }

    return traces;
  }, [property, values, visible, x, y, z]);

  const layout = useMemo(
    () => ({
      autosize: true,
      height: 570,
      margin: { l: 0, r: 0, t: 40, b: 0 },
      showlegend: false,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      title: {
        text: "Dynamic 3D wellbore and depth-property envelope",
        font: { size: 15 },
      },
      scene: {
        bgcolor: "rgba(0,0,0,0)",
        aspectmode: "manual",
        aspectratio: { x: 0.55, y: 0.55, z: 2.2 },
        xaxis: { title: "East offset (m)" },
        yaxis: { title: "North offset (m)" },
        zaxis: { title: "Depth (m)" },
      },
    }),
    [],
  );

  return <SafePlot data={data} layout={layout} minHeight={570} />;
}

export function ReservoirDigitalTwinPanel() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(0);
  const [selectedTwin, setSelectedTwin] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState(
    () => sessionStorage.getItem("petroedge_open_dataset_id") ?? "",
  );
  const [selectedAssetId, setSelectedAssetId] = useState(() => {
    try {
      const stored = JSON.parse(
        sessionStorage.getItem("petroedge_selected_asset") ?? "null",
      ) as { asset_id?: string } | null;
      return stored?.asset_id ?? "";
    } catch {
      return "";
    }
  });
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [property, setProperty] = useState("porosity");
  const [scenarioName, setScenarioName] = useState("Pressure sensitivity");
  const [scenarioPath, setScenarioPath] = useState("");
  const [scenarioOperation, setScenarioOperation] = useState<
    "set" | "increase" | "decrease" | "multiply"
  >("increase");
  const [scenarioValue, setScenarioValue] = useState("1");

  const twins = useQuery({ queryKey: ["twins"], queryFn: fetchTwins });
  const datasets = useQuery({
    queryKey: ["platform", "datasets"],
    queryFn: fetchDatasets,
  });
  const assets = useQuery({ queryKey: ["assets"], queryFn: fetchAssets });

  const twinList = twins.data?.twins ?? [];
  const activeTwinId = selectedTwin || twinList[0]?.reservoir_id || "";
  const activeTwin = twinList.find((item) => item.reservoir_id === activeTwinId);
  const selectedAsset = (assets.data ?? []).find(
    (item) => item.asset_id === selectedAssetId,
  );
  const inferredTwinDatasetId = inferDatasetForTwin(
    activeTwin,
    datasets.data ?? [],
  );
  const activeDatasetId =
    selectedDatasetId ||
    selectedAsset?.dataset_id ||
    inferredTwinDatasetId ||
    datasets.data?.[0]?.dataset_id ||
    "";

  const replay = useQuery({
    queryKey: ["digital-well-twin", "replay", activeDatasetId],
    queryFn: () => fetchReplay(activeDatasetId),
    enabled: Boolean(activeDatasetId),
    staleTime: 60_000,
  });
  const summary = useQuery({
    queryKey: ["twin-workspace", activeTwinId],
    queryFn: () => fetchTwinWorkspaceSummary(activeTwinId),
    enabled: Boolean(activeTwinId),
  });
  const history = useQuery({
    queryKey: ["twin-history", activeTwinId],
    queryFn: () => fetchTwinHistory(activeTwinId),
    enabled: Boolean(activeTwinId),
  });

  const events = (replay.data?.events ?? []) as ReplayEvent[];
  const currentEvent = events[Math.min(index, Math.max(0, events.length - 1))];
  const currentState = eventState(currentEvent);
  const availableScenarioPaths = useMemo(
    () => numericPaths(summary.data?.twin),
    [summary.data?.twin],
  );

  useEffect(() => {
    if (!selectedDatasetId && activeDatasetId) {
      setSelectedDatasetId(activeDatasetId);
    }
  }, [activeDatasetId, selectedDatasetId]);

  useEffect(() => {
    if (!selectedAsset?.dataset_id) return;
    setSelectedDatasetId(selectedAsset.dataset_id);
    sessionStorage.setItem(
      "petroedge_open_dataset_id",
      selectedAsset.dataset_id,
    );
    sessionStorage.setItem(
      "petroedge_selected_asset",
      JSON.stringify(selectedAsset),
    );
  }, [selectedAsset]);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [activeTwinId, activeDatasetId]);

  useEffect(() => {
    if (!playing || events.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex((current) => {
        if (current >= events.length - 1) {
          setPlaying(false);
          return events.length - 1;
        }
        return current + 1;
      });
    }, speeds[speed].delay);
    return () => window.clearInterval(timer);
  }, [events.length, playing, speed]);

  useEffect(() => {
    if (scenarioPath && !availableScenarioPaths.includes(scenarioPath)) {
      setScenarioPath("");
    } else if (!scenarioPath && availableScenarioPaths.length > 0) {
      setScenarioPath(availableScenarioPaths[0]);
    }
  }, [availableScenarioPaths, scenarioPath]);


  const restore = useMutation({
    mutationFn: (version: number) => restoreTwinVersion(activeTwinId, version),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["twin-workspace", activeTwinId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["twin-history", activeTwinId],
        }),
      ]);
    },
  });

  const scenario = useMutation({
    mutationFn: () =>
      runTwinWorkspaceScenario(activeTwinId, {
        name: scenarioName,
        adjustments: [
          {
            path: scenarioPath,
            operation: scenarioOperation,
            value: Number(scenarioValue),
          },
        ],
      }),
  });

  const loading = twins.isLoading || datasets.isLoading || assets.isLoading;
  const metricCards: Array<[string, string, ReactNode]> = [
    ["Depth", currentEvent ? `${currentEvent.depth.toFixed(1)} m` : "—", <Waves size={18} />],
    ["Porosity", currentEvent ? percent(currentState.porosity) : "—", <Gauge size={18} />],
    ["Water saturation", currentEvent ? percent(currentState.water_saturation) : "—", <Activity size={18} />],
    ["Hydrocarbon", currentEvent ? percent(currentState.hydrocarbon_probability) : "—", <Database size={18} />],
    ["Pressure", currentEvent ? `${numberValue(currentState.pressure).toFixed(1)} MPa` : "—", <Gauge size={18} />],
    ["Temperature", currentEvent ? `${numberValue(currentState.temperature).toFixed(1)} °C` : "—", <Activity size={18} />],
  ];

  return (
    <Stack spacing={3}>
      <Paper className="feature-hero" sx={{ p: { xs: 3, md: 4 } }}>
        <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
          <Box>
            <Chip label="Living virtual well" className="hero-chip" />
            <Stack direction="row" gap={1.5} alignItems="center" mt={1.2}>
              <Cube />
              <Typography variant="h4" fontWeight={900}>Digital Well Twin</Typography>
            </Stack>
            <Typography mt={1}>
              A dynamic well model driven by historical replay today and designed for IoT, WITSML, SCADA and edge feeds.
            </Typography>
          </Box>
          <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            <Chip
              icon={<Radio size={15} />}
              color={playing ? "success" : "default"}
              label={playing ? "Simulation live" : "Twin ready"}
            />
            <Button
              startIcon={<RefreshCw size={16} />}
              onClick={() => {
                void twins.refetch();
                void datasets.refetch();
                void assets.refetch();
                if (activeTwinId) {
                  void summary.refetch();
                  void history.refetch();
                }
              }}
            >
              Refresh
            </Button>
            <Button
              variant="outlined"
              startIcon={<Database size={16} />}
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("petroedge:navigate", {
                    detail: { tab: "Datasets" },
                  }),
                )
              }
            >
              Datasets
            </Button>
            <Button
              variant="contained"
              startIcon={<Cube size={16} />}
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("petroedge:navigate", {
                    detail: { tab: "Assets" },
                  }),
                )
              }
            >
              Assets
            </Button>
          </Stack>
        </Stack>
      </Paper>

      {loading && <LinearProgress />}
      {(twins.isError || datasets.isError || assets.isError) && (
        <Alert severity="error">
          One or more Digital Well Twin services could not load. Refresh after confirming the API and session are active.
        </Alert>
      )}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Well dataset</InputLabel>
              <Select
                label="Well dataset"
                value={activeDatasetId}
                onChange={(event) => {
                  const nextDatasetId = event.target.value;
                  setSelectedDatasetId(nextDatasetId);
                  sessionStorage.setItem(
                    "petroedge_open_dataset_id",
                    nextDatasetId,
                  );
                  const linkedAsset = (assets.data ?? []).find(
                    (item) => item.dataset_id === nextDatasetId,
                  );
                  if (linkedAsset) {
                    setSelectedAssetId(linkedAsset.asset_id);
                    sessionStorage.setItem(
                      "petroedge_selected_asset",
                      JSON.stringify(linkedAsset),
                    );
                  }
                }}
              >
                <MenuItem value="">Select a dataset</MenuItem>
                {(datasets.data ?? []).map((dataset) => (
                  <MenuItem key={dataset.dataset_id} value={dataset.dataset_id}>
                    {dataset.name}
                    {dataset.well_name ? ` · ${dataset.well_name}` : ""}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <FormControl fullWidth>
              <InputLabel>Registered well asset</InputLabel>
              <Select
                label="Registered well asset"
                value={selectedAssetId}
                onChange={(event) => {
                  const nextAssetId = event.target.value;
                  setSelectedAssetId(nextAssetId);
                  const nextAsset = (assets.data ?? []).find(
                    (item) => item.asset_id === nextAssetId,
                  );
                  if (nextAsset?.dataset_id) {
                    setSelectedDatasetId(nextAsset.dataset_id);
                    sessionStorage.setItem(
                      "petroedge_open_dataset_id",
                      nextAsset.dataset_id,
                    );
                  }
                  if (nextAsset) {
                    sessionStorage.setItem(
                      "petroedge_selected_asset",
                      JSON.stringify(nextAsset),
                    );
                  }
                }}
              >
                <MenuItem value="">Select an asset</MenuItem>
                {(assets.data ?? []).map((asset) => (
                  <MenuItem key={asset.asset_id} value={asset.asset_id}>
                    {asset.field} · {asset.well}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>3D property</InputLabel>
              <Select
                label="3D property"
                value={property}
                onChange={(event) => setProperty(event.target.value)}
              >
                {[
                  "porosity",
                  "water_saturation",
                  "hydrocarbon_probability",
                  "permeability",
                  "gamma_ray",
                  "anomaly_score",
                ].map((item) => (
                  <MenuItem key={item} value={item}>
                    {item.replace(/_/g, " ")}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={3}>
            <Stack direction="row" gap={1}>
              <Button
                fullWidth
                variant="contained"
                disabled={events.length === 0}
                startIcon={playing ? <Pause /> : <Play />}
                onClick={() => setPlaying((value) => !value)}
              >
                {playing ? "Pause" : "Start simulation"}
              </Button>
              <Button
                startIcon={<RotateCcw />}
                onClick={() => {
                  setIndex(0);
                  setPlaying(false);
                }}
              >
                Reset
              </Button>
            </Stack>
          </Grid>
        </Grid>

        {twinList.length > 0 && (
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel>Optional persisted engineering state</InputLabel>
            <Select
              label="Optional persisted engineering state"
              value={activeTwinId}
              onChange={(event) => setSelectedTwin(event.target.value)}
            >
              <MenuItem value="">Dataset replay only</MenuItem>
              {twinList.map((twin) => (
                <MenuItem key={twin.reservoir_id} value={twin.reservoir_id}>
                  {twin.name} · {twin.reservoir_id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Paper>

      {!activeDatasetId && !loading && (
        <Alert severity="info">
          Select a well dataset or a registered asset to initialise the Digital Well Twin. Datasets and Assets are the platform source of truth; no separate twin-creation step is required.
        </Alert>
      )}

      {activeDatasetId && (
        <>
          {selectedAssetId && !selectedAsset?.dataset_id && (
            <Alert severity="warning">
              The selected asset has no linked dataset. Assign a dataset in Assets or select a dataset directly.
            </Alert>
          )}

          <Grid container spacing={2}>
            {metricCards.map(([label, value, icon]) => (
              <Grid item xs={6} md={2} key={label}>
                <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                  <Stack direction="row" gap={1} alignItems="center">
                    {icon}
                    <Typography variant="caption">{label}</Typography>
                  </Stack>
                  <Typography variant="h6" mt={1}>{value}</Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>

          <Paper variant="outlined">
            <Tabs
              value={tab}
              onChange={(_event, value) => setTab(value)}
              variant="scrollable"
              scrollButtons="auto"
            >
              <Tab label="3D Live Twin" />
              <Tab label="Live State" />
              <Tab label="Hybrid Models" />
              <Tab label="Predictions" />
              <Tab label="Maintenance & Alerts" />
              <Tab label="Scenario" />
              <Tab label="Version History" />
            </Tabs>
          </Paper>

          {replay.isLoading && <LinearProgress />}
          {replay.isError && (
            <Alert severity="error">
              The selected dataset replay could not be loaded.
            </Alert>
          )}

          {tab === 0 && (
            <Stack spacing={2}>
              <Paper variant="outlined" sx={{ p: 1 }}>
                {events.length > 0 ? (
                  <DynamicWell3D events={events} index={index} property={property} />
                ) : (
                  <Alert severity="info">No replay states are available for the selected dataset.</Alert>
                )}
              </Paper>
              <Paper variant="outlined" sx={{ p: 2.5 }}>
                <Stack direction={{ xs: "column", md: "row" }} gap={2} alignItems="center">
                  <Button
                    variant="contained"
                    disabled={events.length === 0}
                    startIcon={playing ? <Pause /> : <Play />}
                    onClick={() => setPlaying((value) => !value)}
                  >
                    {playing ? "Pause" : "Play"}
                  </Button>
                  <Slider
                    value={index}
                    min={0}
                    max={Math.max(0, events.length - 1)}
                    onChange={(_event, value) => {
                      setIndex(Number(value));
                      setPlaying(false);
                    }}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(value) =>
                      events[value] ? `${events[value].depth.toFixed(1)} m` : "—"
                    }
                    sx={{ flex: 1 }}
                  />
                  <FormControl sx={{ minWidth: 120 }}>
                    <InputLabel>Speed</InputLabel>
                    <Select
                      label="Speed"
                      value={speed}
                      onChange={(event) => setSpeed(Number(event.target.value))}
                    >
                      {speeds.map((item, speedIndex) => (
                        <MenuItem key={item.label} value={speedIndex}>
                          {item.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <Chip label={`${events.length} states`} />
                </Stack>
              </Paper>
            </Stack>
          )}

          {tab === 1 && (
            <Grid container spacing={2}>
              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
                  <Typography variant="h6">Current well state</Typography>
                  <Stack spacing={1.2} mt={2}>
                    {Object.entries(currentState).map(([key, value]) => (
                      <Stack direction="row" justifyContent="space-between" key={key}>
                        <Typography color="text.secondary">
                          {key.replace(/_/g, " ")}
                        </Typography>
                        <Typography fontWeight={700}>{display(value)}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                </Paper>
              </Grid>
              <Grid item xs={12} md={7}>
                <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
                  <Typography variant="h6">Incoming measurements</Typography>
                  <Grid container spacing={2} mt={0.5}>
                    {Object.entries(currentEvent?.logs ?? {}).map(([key, value]) => (
                      <Grid item xs={6} md={4} key={key}>
                        <Typography variant="caption" color="text.secondary">
                          {key.toUpperCase()}
                        </Typography>
                        <Typography fontWeight={800}>{numberValue(value).toFixed(3)}</Typography>
                      </Grid>
                    ))}
                  </Grid>
                </Paper>
              </Grid>
            </Grid>
          )}

          {tab === 2 && (
            <Grid container spacing={2}>
              {[
                ["Physics and petrophysics", "Porosity, saturation, permeability and depth-derived pressure and temperature baselines."],
                ["AI temporal inference", "GRU causal inference, BiGRU replay, lithology classification, anomaly detection and property prediction."],
                ["Hybrid reconciliation", "Physics and AI outputs share one state with transparent provenance and engineering thresholds."],
                ["Edge execution", "CPU-first deployment, simulated streaming, offline replay and queued synchronisation."],
              ].map(([title, detail]) => (
                <Grid item xs={12} md={6} key={title}>
                  <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
                    <Typography variant="h6">{title}</Typography>
                    <Typography color="text.secondary" mt={1}>{detail}</Typography>
                    <Chip size="small" color="success" sx={{ mt: 2 }} label="Connected architecture" />
                  </Paper>
                </Grid>
              ))}
            </Grid>
          )}

          {tab === 3 && (
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Typography variant="h6">Prediction and optimisation</Typography>
              <Stack direction="row" gap={1} flexWrap="wrap" mt={2}>
                <Chip label={String(currentState.lithology ?? "Unknown")} />
                <Chip
                  color={currentState.pay_flag === "Pay" ? "success" : "default"}
                  label={String(currentState.pay_flag ?? "Non-pay")}
                />
                <Chip label={`Permeability ${numberValue(currentState.permeability).toFixed(1)} mD`} />
              </Stack>
              <Alert
                severity={numberValue(currentState.hydrocarbon_probability) > 0.6 ? "success" : "info"}
                sx={{ mt: 2 }}
              >
                {numberValue(currentState.hydrocarbon_probability) > 0.6
                  ? "Prioritise this interval for reservoir review and correlation."
                  : "Continue simulation; this interval remains below the hydrocarbon screening threshold."}
              </Alert>
            </Paper>
          )}

          {tab === 4 && (
            <Stack spacing={2}>
              {(currentEvent?.alerts ?? []).length > 0 ? (
                currentEvent?.alerts.map((item) => (
                  <Alert severity="warning" key={item}>{item}</Alert>
                ))
              ) : (
                <Alert severity="success">No active anomaly or data-quality alert at this depth.</Alert>
              )}
              <Paper variant="outlined" sx={{ p: 3 }}>
                <Typography variant="h6">Maintenance rules</Typography>
                <Typography color="text.secondary" mt={1}>
                  Sensor drift, stuck values, missing curves, borehole enlargement, abnormal pressure or temperature, communication loss and model-confidence degradation.
                </Typography>
              </Paper>
            </Stack>
          )}

          {tab === 5 && (
            !activeTwinId ? (
              <Alert severity="info">
                Dataset replay is active. Select an optional persisted engineering state above to run saved-state scenarios.
              </Alert>
            ) : (
            <Grid container spacing={2}>
              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 3 }}>
                  <Stack spacing={2}>
                    <Typography variant="h6">Engineering sensitivity scenario</Typography>
                    <TextField
                      label="Scenario name"
                      value={scenarioName}
                      onChange={(event) => setScenarioName(event.target.value)}
                    />
                    {availableScenarioPaths.length > 0 ? (
                      <FormControl>
                        <InputLabel>State path</InputLabel>
                        <Select
                          label="State path"
                          value={scenarioPath}
                          onChange={(event) => setScenarioPath(event.target.value)}
                        >
                          {availableScenarioPaths.map((item) => (
                            <MenuItem key={item} value={item}>{item}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : (
                      <Alert severity="info">
                        The backend twin has no numeric persisted state yet. The live 3D replay remains available, but scenarios require a populated twin state.
                      </Alert>
                    )}
                    <FormControl>
                      <InputLabel>Operation</InputLabel>
                      <Select
                        label="Operation"
                        value={scenarioOperation}
                        onChange={(event) =>
                          setScenarioOperation(
                            event.target.value as "set" | "increase" | "decrease" | "multiply",
                          )
                        }
                      >
                        {[
                          "set",
                          "increase",
                          "decrease",
                          "multiply",
                        ].map((item) => (
                          <MenuItem key={item} value={item}>{item}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <TextField
                      type="number"
                      label="Value"
                      value={scenarioValue}
                      onChange={(event) => setScenarioValue(event.target.value)}
                    />
                    <Button
                      variant="contained"
                      startIcon={<Play />}
                      disabled={
                        !activeTwinId ||
                        scenarioName.trim().length < 2 ||
                        !availableScenarioPaths.includes(scenarioPath) ||
                        !Number.isFinite(Number(scenarioValue)) ||
                        scenario.isPending
                      }
                      onClick={() => scenario.mutate()}
                    >
                      {scenario.isPending ? "Running…" : "Compare scenario"}
                    </Button>
                  </Stack>
                </Paper>
              </Grid>
              <Grid item xs={12} md={7}>
                <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
                  <Typography variant="h6">Scenario delta</Typography>
                  {!scenario.data ? (
                    <Typography color="text.secondary" mt={1}>
                      Run a scenario to compare baseline and adjusted persisted state values.
                    </Typography>
                  ) : (
                    <Stack spacing={1.5} mt={2}>
                      {scenario.data.changes.map((change) => (
                        <Paper key={change.path} variant="outlined" sx={{ p: 2 }}>
                          <Typography fontWeight={800}>{change.path}</Typography>
                          <Stack direction="row" gap={1} mt={1} flexWrap="wrap">
                            <Chip label={`Baseline: ${display(change.before)}`} />
                            <Chip color="primary" label={`Scenario: ${display(change.after)}`} />
                            <Chip label={change.operation} />
                          </Stack>
                        </Paper>
                      ))}
                      <Alert severity="warning">{scenario.data.warning}</Alert>
                    </Stack>
                  )}
                </Paper>
              </Grid>
            </Grid>
            )
          )}

          {tab === 6 && (
            !activeTwinId ? (
              <Alert severity="info">
                Dataset replay does not require a persisted twin record. Select an optional persisted engineering state above to inspect version history.
              </Alert>
            ) : (
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Stack direction="row" gap={1} alignItems="center" mb={2}>
                <History size={18} />
                <Typography variant="h6">Version history</Typography>
                <Chip
                  icon={<ShieldCheck size={15} />}
                  label={`${history.data?.count ?? 0} versions`}
                />
              </Stack>
              {history.isLoading && <LinearProgress />}
              <Stack spacing={1.5}>
                {(history.data?.snapshots ?? [])
                  .slice()
                  .reverse()
                  .map((snapshot, snapshotIndex) => {
                    const version = Number(
                      snapshot.version ?? (history.data?.count ?? 0) - snapshotIndex,
                    );
                    return (
                      <Paper variant="outlined" sx={{ p: 2 }} key={`${version}-${snapshotIndex}`}>
                        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between">
                          <Box>
                            <Typography fontWeight={800}>Version {version}</Typography>
                            <Typography variant="body2" color="text.secondary">
                              {display(snapshot.created_at ?? snapshot.timestamp)}
                            </Typography>
                          </Box>
                          <Button
                            startIcon={<RotateCcw />}
                            disabled={restore.isPending}
                            onClick={() => restore.mutate(version)}
                          >
                            Restore
                          </Button>
                        </Stack>
                      </Paper>
                    );
                  })}
              </Stack>
            </Paper>
            )
          )}
        </>
      )}

    </Stack>
  );
}
