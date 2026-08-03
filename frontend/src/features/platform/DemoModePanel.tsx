import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, Grid, LinearProgress, Paper, Stack, Step, StepLabel, Stepper, Typography } from "@mui/material";
import { CheckCircle2, FileDown, PlayCircle, Presentation, RotateCcw } from "lucide-react";
import { analyzeSample, fetchLogs } from "../../api/client";
import type { AnalyticsResult } from "../../api/types";

const steps = ["Load demo well", "Run QC", "AI inference", "Petrophysics", "Decision summary"];

export function DemoModePanel() {
  const [active, setActive] = useState(0);
  const [result, setResult] = useState<AnalyticsResult | null>(null);
  const [running, setRunning] = useState(false);
  const logs = useQuery({ queryKey: ["logs", "PETROEDGE-DEMO-01"], queryFn: () => fetchLogs("PETROEDGE-DEMO-01") });
  const sample = useMemo(() => logs.data && logs.data.length ? logs.data[logs.data.length - 1] : undefined, [logs.data]);
  async function runDemo() {
    if (!sample) return;
    setRunning(true); setResult(null);
    try {
      for (let i = 1; i < steps.length; i += 1) { await new Promise((resolve) => setTimeout(resolve, 350)); setActive(i); }
      setResult(await analyzeSample(sample));
    } finally { setRunning(false); }
  }
  function reset() { setActive(0); setResult(null); }
  return <Stack spacing={3}>
    <Paper className="demo-hero" sx={{ p: { xs: 3, md: 5 } }}><Grid container spacing={3} alignItems="center"><Grid item xs={12} md={8}><Chip icon={<Presentation size={15}/>} label="Competition presentation mode" className="hero-chip"/><Typography variant="h3" fontWeight={850} mt={2}>From well logs to a decision in one workflow</Typography><Typography sx={{ mt: 1.5, opacity: .87, maxWidth: 760 }}>Demonstrate PetroEdge using a preloaded Nigerian reservoir interval. The workflow executes quality control, AI inference and petrophysical interpretation without requiring a live rig connection.</Typography></Grid><Grid item xs={12} md={4}><Stack gap={1.5}><Button size="large" variant="contained" startIcon={<PlayCircle/>} onClick={() => void runDemo()} disabled={!sample || running}>{running ? "Running demonstration…" : "Start guided demo"}</Button><Button size="large" color="inherit" startIcon={<RotateCcw/>} onClick={reset}>Reset</Button></Stack></Grid></Grid></Paper>
    {logs.isLoading && <LinearProgress/>}{logs.isError && <Alert severity="error">The demonstration well could not be loaded.</Alert>}
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}><Stepper activeStep={active} alternativeLabel>{steps.map((label) => <Step key={label} completed={Boolean(result) || active > steps.indexOf(label)}><StepLabel>{label}</StepLabel></Step>)}</Stepper></Paper>
    <Grid container spacing={2}>
      <Grid item xs={12} md={7}><Paper variant="outlined" sx={{ p: 3, minHeight: 290 }}><Typography variant="h6">Demo execution</Typography><Stack spacing={1.5} mt={2}>{steps.map((step, index) => <Stack direction="row" gap={1.5} alignItems="center" key={step}><CheckCircle2 size={19} color={active >= index ? "#007c89" : "#aab2bd"}/><Box><Typography fontWeight={active === index ? 750 : 500}>{step}</Typography><Typography variant="caption" color="text.secondary">{active > index || result ? "Completed" : active === index ? running ? "In progress" : "Ready" : "Pending"}</Typography></Box></Stack>)}</Stack></Paper></Grid>
      <Grid item xs={12} md={5}><Paper variant="outlined" sx={{ p: 3, minHeight: 290 }}><Typography variant="h6">Decision summary</Typography>{result ? <Stack spacing={1.5} mt={2}><Box><Typography variant="caption" color="text.secondary">Lithology</Typography><Typography variant="h6">{result.lithology}</Typography></Box><Box><Typography variant="caption" color="text.secondary">Porosity</Typography><Typography variant="h6">{(result.porosity * 100).toFixed(1)}%</Typography></Box><Box><Typography variant="caption" color="text.secondary">Hydrocarbon probability</Typography><Typography variant="h6">{(result.hydrocarbon_probability * 100).toFixed(1)}%</Typography></Box><Alert severity={result.hydrocarbon_probability >= .5 ? "success" : "warning"}>{result.hydrocarbon_probability >= .5 ? "Hydrocarbon-bearing interval indicated. Prioritise review and correlation." : "Evidence is below the decision threshold. Review uncertainty and adjacent depths."}</Alert><Button startIcon={<FileDown size={17}/>} disabled>PDF report export · Phase 3.1</Button></Stack> : <Box py={7} textAlign="center"><Presentation size={43}/><Typography mt={1} color="text.secondary">Run the guided demo to generate a decision summary.</Typography></Box>}</Paper></Grid>
    </Grid>
  </Stack>;
}
