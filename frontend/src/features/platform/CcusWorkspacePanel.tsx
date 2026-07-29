import { useQuery } from "@tanstack/react-query";
import { Alert, Chip, Grid, LinearProgress, Paper, Stack, Typography } from "@mui/material";
import { Database, Gauge, Layers3, ShieldCheck, Waves } from "lucide-react";
import { fetchDatasets } from "./platformApi";

const capabilities = [
  { title: "Storage screening", detail: "Reservoir depth, thickness, porosity and permeability screening.", icon: <Layers3 size={20} /> },
  { title: "Injectivity", detail: "Pressure, permeability and anticipated injection-rate assessment.", icon: <Gauge size={20} /> },
  { title: "Containment", detail: "Seal, fault and pressure-risk evidence management.", icon: <ShieldCheck size={20} /> },
  { title: "Monitoring", detail: "Injection, pressure and plume-monitoring dataset readiness.", icon: <Waves size={20} /> },
];

export function CcusWorkspacePanel() {
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: fetchDatasets });
  if (datasets.isLoading) return <LinearProgress />;

  return (
    <Stack spacing={3}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
        <div>
          <Typography variant="h4" fontWeight={750}>CCUS</Typography>
          <Typography color="text.secondary">
            Carbon capture, utilisation and storage screening workspace. Release 1 establishes the deployment-safe interface boundary; scientific calculations will be added in the dedicated CCUS release.
          </Typography>
        </div>
        <Chip icon={<Database size={16} />} label={`${datasets.data?.length ?? 0} registered datasets`} />
      </Stack>

      <Alert severity="info">
        This workspace is intentionally capability-gated in Release 1. It does not fabricate storage capacity, injectivity or containment results before the required calibrated backend service is installed.
      </Alert>

      <Grid container spacing={2}>
        {capabilities.map((item) => (
          <Grid item xs={12} md={6} key={item.title}>
            <Paper variant="outlined" sx={{ p: 3, height: "100%" }}>
              <Stack spacing={1.5}>
                <Stack direction="row" gap={1} alignItems="center">
                  {item.icon}
                  <Typography variant="h6">{item.title}</Typography>
                </Stack>
                <Typography color="text.secondary">{item.detail}</Typography>
                <Chip label="Backend implementation scheduled" size="small" sx={{ alignSelf: "flex-start" }} />
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
}
