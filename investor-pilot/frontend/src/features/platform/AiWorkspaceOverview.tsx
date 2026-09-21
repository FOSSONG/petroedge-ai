import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import {
  BrainCircuit,
  CheckCircle2,
  Database,
  FlaskConical,
  Layers3,
  RefreshCw,
  Rocket,
  ShieldCheck,
} from "lucide-react";
import { fetchPlatformOverview } from "./platformApi";

const cards = [
  ["datasets", "Registered datasets", Database],
  ["experiments", "Experiments", FlaskConical],
  ["completed_experiments", "Completed runs", CheckCircle2],
  ["registered_models", "Registered models", BrainCircuit],
  ["production_models", "Production models", Rocket],
] as const;

const label = (value: string) => value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());

export function AiWorkspaceOverview() {
  const query = useQuery({
    queryKey: ["platform", "overview"],
    queryFn: fetchPlatformOverview,
    refetchInterval: 60_000,
  });

  if (query.isLoading) return <LinearProgress />;
  if (query.isError) {
    return (
      <Alert severity="error" action={<Button onClick={() => void query.refetch()}>Retry</Button>}>
        {query.error instanceof Error ? query.error.message : "Unable to load AI workspace."}
      </Alert>
    );
  }

  const data = query.data!;

  return (
    <Stack spacing={3}>
      <Paper
        elevation={0}
        className="ai-workspace-hero"
        sx={{
          p: { xs: 3, md: 4 },
          overflow: "hidden",
          position: "relative",
          isolation: "isolate",
          backgroundColor: "#043942 !important",
          backgroundImage: "linear-gradient(135deg, #043942 0%, #006d78 58%, #0a8f83 100%) !important",
          border: "1px solid rgba(82, 232, 220, 0.58)",
          boxShadow: "0 20px 54px rgba(1, 47, 55, 0.34)",
          color: "#ffffff !important",
        }}
      >
        <Box sx={{ maxWidth: 780, position: "relative", zIndex: 2 }}>
          <Chip
            icon={<ShieldCheck size={15} color="#ffffff" />}
            label={`Platform ${data.version}`}
            size="small"
            sx={{
              mb: 2,
              bgcolor: "rgba(255,255,255,.18) !important",
              color: "#ffffff !important",
              border: "1px solid rgba(255,255,255,.42)",
              "& .MuiChip-label": { color: "#ffffff !important", fontWeight: 800 },
              "& .MuiChip-icon": { color: "#ffffff !important" },
            }}
          />
          <Typography
            variant="h4"
            fontWeight={900}
            sx={{ color: "#ffffff !important", opacity: "1 !important", textShadow: "0 2px 16px rgba(0,0,0,.28)" }}
          >
            AI Workspace
          </Typography>
          <Typography
            sx={{
              mt: 1.25,
              maxWidth: 720,
              color: "#f4ffff !important",
              opacity: "1 !important",
              fontSize: { xs: "1rem", md: "1.08rem" },
              lineHeight: 1.65,
              fontWeight: 500,
              textShadow: "0 1px 10px rgba(0,0,0,.22)",
            }}
          >
            Manage datasets, experiments and deployable geoscience models from one sovereign, model-independent workspace.
          </Typography>
        </Box>
        <Layers3
          size={190}
          color="#b8fff7"
          style={{ position: "absolute", right: 22, top: -22, opacity: 0.18, zIndex: 1 }}
        />
      </Paper>

      <Paper className="workflow-card" sx={{ p: { xs: 3, md: 4 } }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <Typography variant="overline" fontWeight={800}>AI workflow</Typography>
            <Typography variant="h5" fontWeight={850}>From uploaded logs to an auditable reservoir decision</Typography>
            <Typography sx={{ mt: 1, color: "rgba(255,255,255,.94)" }}>
              Upload → quality control → curve visualisation → model training → interpretation → branded PDF report.
            </Typography>
            <Stack direction="row" gap={1} mt={2} flexWrap="wrap">
              {["Upload", "QC", "Visualise", "Train", "Interpret", "Report"].map((step, index) => (
                <Chip key={step} label={`${index + 1}. ${step}`} className="workflow-step" />
              ))}
            </Stack>
          </Grid>
          <Grid item xs={12} md={4}>
            <Box
              component="img"
              src="/petroedge-logo.png"
              alt="PetroEdge AI"
              sx={{ width: "100%", maxHeight: 190, objectFit: "cover", borderRadius: 2, boxShadow: "0 18px 45px rgba(0,0,0,.28)" }}
            />
          </Grid>
        </Grid>
      </Paper>

      <Grid container spacing={2}>
        {cards.map(([key, title, Icon]) => (
          <Grid item xs={12} sm={6} lg key={key}>
            <Paper variant="outlined" sx={{ p: 2.5, height: "100%" }}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="body2" color="text.secondary">{title}</Typography>
                  <Typography variant="h4" mt={0.5}>{data[key].toLocaleString()}</Typography>
                </Box>
                <Box sx={{ p: 1.1, borderRadius: 2, bgcolor: "rgba(0,124,137,.09)", color: "primary.main" }}>
                  <Icon size={22} />
                </Box>
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={2} mb={2}>
          <Box>
            <Typography variant="h6">Platform capabilities</Typography>
            <Typography variant="body2" color="text.secondary">Services available in the current MVP deployment.</Typography>
          </Box>
          <Button startIcon={<RefreshCw size={16} />} onClick={() => void query.refetch()}>Refresh</Button>
        </Stack>
        <Stack direction="row" gap={1} flexWrap="wrap">
          {data.capabilities.map((item) => <Chip key={item} label={label(item)} variant="outlined" />)}
        </Stack>
      </Paper>
    </Stack>
  );
}
