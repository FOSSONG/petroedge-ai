import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Typography,
} from "@mui/material";
import { Play, Workflow } from "lucide-react";
import { fetchDatasetPreview, fetchDatasets } from "./platformApi";
import { fetchWorkflows, runWorkflow } from "./workflowApi";

function statusColour(status: string) {
  if (status === "succeeded") return "success" as const;
  if (status === "failed") return "error" as const;
  if (status === "running") return "warning" as const;
  return "default" as const;
}

export function AiWorkflowsPanel() {
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: fetchWorkflows });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: fetchDatasets });
  const [workflowId, setWorkflowId] = useState("");
  const [datasetId, setDatasetId] = useState("");

  useEffect(() => {
    if (!workflowId && workflows.data?.workflows.length) {
      setWorkflowId(workflows.data.workflows[0].id);
    }
  }, [workflowId, workflows.data]);

  useEffect(() => {
    if (!datasetId && datasets.data?.length) {
      setDatasetId(datasets.data[0].dataset_id);
    }
  }, [datasetId, datasets.data]);

  const selectedWorkflow = useMemo(
    () => workflows.data?.workflows.find((item) => item.id === workflowId),
    [workflowId, workflows.data],
  );

  const mutation = useMutation({
    mutationFn: async () => {
      const preview = await fetchDatasetPreview(datasetId);
      return runWorkflow(workflowId, preview.rows, datasetId);
    },
  });

  if (workflows.isLoading || datasets.isLoading) {
    return <LinearProgress />;
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={750}>AI Workflows</Typography>
        <Typography color="text.secondary">
          Execute governed, repeatable petroleum workflows using registered datasets and the existing backend workflow engine.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={5}>
            <FormControl fullWidth>
              <InputLabel>Workflow</InputLabel>
              <Select label="Workflow" value={workflowId} onChange={(event) => setWorkflowId(event.target.value)}>
                {(workflows.data?.workflows ?? []).map((item) => (
                  <MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={5}>
            <FormControl fullWidth>
              <InputLabel>Dataset</InputLabel>
              <Select label="Dataset" value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
                {(datasets.data ?? []).map((item) => (
                  <MenuItem key={item.dataset_id} value={item.dataset_id}>{item.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <Button
              fullWidth
              sx={{ height: 56 }}
              variant="contained"
              startIcon={mutation.isPending ? <CircularProgress size={18} color="inherit" /> : <Play size={18} />}
              disabled={!workflowId || !datasetId || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Running" : "Run"}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {selectedWorkflow && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1}>
              <Box>
                <Typography variant="h6">{selectedWorkflow.name}</Typography>
                <Typography color="text.secondary">{selectedWorkflow.description}</Typography>
              </Box>
              <Stack direction="row" gap={1} flexWrap="wrap">
                {selectedWorkflow.tags.map((tag) => <Chip key={tag} label={tag} size="small" />)}
              </Stack>
            </Stack>
            <Stepper alternativeLabel activeStep={-1}>
              {selectedWorkflow.nodes.filter((node) => node.enabled).map((node) => (
                <Step key={node.id} completed={false}>
                  <StepLabel>{node.name ?? node.id.replace(/[-_]/g, " ")}</StepLabel>
                </Step>
              ))}
            </Stepper>
          </Stack>
        </Paper>
      )}

      {mutation.isError && (
        <Alert severity="error">{mutation.error instanceof Error ? mutation.error.message : "Workflow execution failed."}</Alert>
      )}

      {mutation.data && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Stack direction="row" gap={1} alignItems="center">
              <Workflow size={20} />
              <Typography variant="h6">Run {mutation.data.run_id.slice(0, 12)}</Typography>
              <Chip label={mutation.data.status} color={statusColour(mutation.data.status)} size="small" />
            </Stack>
            {mutation.data.error && <Alert severity="error">{mutation.data.error}</Alert>}
            <Grid container spacing={2}>
              {mutation.data.node_results.map((node) => (
                <Grid item xs={12} md={6} lg={4} key={node.node_id}>
                  <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                    <Stack spacing={1}>
                      <Stack direction="row" justifyContent="space-between" gap={1}>
                        <Typography fontWeight={700}>{node.node_id.replace(/[-_]/g, " ")}</Typography>
                        <Chip label={node.status} color={statusColour(node.status)} size="small" />
                      </Stack>
                      <Typography variant="caption" color="text.secondary">{node.node_type}</Typography>
                      <Typography variant="body2">
                        {Object.keys(node.output ?? {}).length} output field{Object.keys(node.output ?? {}).length === 1 ? "" : "s"}
                      </Typography>
                      {node.error && <Alert severity="error">{node.error}</Alert>}
                    </Stack>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </Stack>
        </Paper>
      )}

      {!datasets.data?.length && (
        <Alert severity="info">Upload a dataset before running a workflow.</Alert>
      )}
    </Stack>
  );
}
