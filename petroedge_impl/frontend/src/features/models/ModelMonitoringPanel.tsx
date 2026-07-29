import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  DatabaseZap,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { fetchModelStatus } from "../../api/client";
import { ApiError } from "../../api/http";
import type { ModelStatus } from "../../api/types";

function formatLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }

  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, {
          maximumFractionDigits: 4,
        });
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value)) {
    return `${value.length} items`;
  }

  return Object.entries(value as Record<string, unknown>).map(([key, item]) => `${formatLabel(key)}: ${String(item)}`).join(" · ");
}

function modelErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return (
        "The model service cannot be reached. " +
        "Confirm that the FastAPI backend is running."
      );
    }

    if (error.status === 401) {
      return "Your session has expired.";
    }

    if (error.status === 403) {
      return "Your account cannot access model monitoring.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Model status could not be loaded.";
}

interface ModelCardProps {
  model: unknown;
  index: number;
}

function ModelCard({
  model,
  index,
}: ModelCardProps) {
  if (
    typeof model !== "object" ||
    model === null
  ) {
    return (
      <Paper
        variant="outlined"
        sx={{ p: 2.5 }}
      >
        <Typography variant="h6">
          Model {index + 1}
        </Typography>

        <Typography color="text.secondary">
          {formatValue(model)}
        </Typography>
      </Paper>
    );
  }

  const record = model as Record<string, unknown>;

  const name =
    String(
      record.name ??
        record.model_name ??
        record.id ??
        `Model ${index + 1}`,
    );

  const status =
    String(
      record.status ??
        record.state ??
        "registered",
    );

  return (
    <Paper
      variant="outlined"
      sx={{ p: 2.5 }}
    >
      <Stack
        direction={{
          xs: "column",
          sm: "row",
        }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{
          xs: "flex-start",
          sm: "center",
        }}
      >
        <Box>
          <Typography variant="h6">
            {name}
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
          >
            Registered inference model
          </Typography>
        </Box>

        <Chip
          label={status}
          color={
            ["active", "healthy", "ready", "registered"].includes(
              status.toLowerCase(),
            )
              ? "success"
              : "default"
          }
          size="small"
        />
      </Stack>

      <Divider sx={{ my: 2 }} />

      <Stack spacing={1}>
        {Object.entries(record)
          .filter(
            ([key]) =>
              !["name", "model_name", "id", "status", "state"].includes(
                key,
              ),
          )
          .map(([key, value]) => (
            <Stack
              key={key}
              direction="row"
              spacing={2}
              justifyContent="space-between"
            >
              <Typography
                variant="body2"
                color="text.secondary"
              >
                {formatLabel(key)}
              </Typography>

              <Typography
                variant="body2"
                textAlign="right"
              >
                {formatValue(value)}
              </Typography>
            </Stack>
          ))}
      </Stack>
    </Paper>
  );
}

export function ModelMonitoringPanel() {
  const modelsQuery = useQuery<ModelStatus>({
    queryKey: ["models"],
    queryFn: fetchModelStatus,
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    retry: (failureCount, error) => {
      if (
        error instanceof ApiError &&
        [401, 403, 404, 422].includes(error.status)
      ) {
        return false;
      }

      return failureCount < 2;
    },
  });

  const registeredModels = useMemo(
    () =>
      modelsQuery.data?.registered_models ?? [],
    [modelsQuery.data],
  );

  const detailedModels = useMemo(
    () =>
      Array.isArray(modelsQuery.data?.models)
        ? modelsQuery.data.models
        : [],
    [modelsQuery.data],
  );

  if (modelsQuery.isLoading) {
    return (
      <Box
        minHeight={300}
        display="grid"
        sx={{ placeItems: "center" }}
      >
        <Stack
          spacing={2}
          alignItems="center"
        >
          <CircularProgress />

          <Typography color="text.secondary">
            Loading model registry...
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (modelsQuery.isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button
            color="inherit"
            size="small"
            onClick={() =>
              void modelsQuery.refetch()
            }
          >
            Retry
          </Button>
        }
      >
        {modelErrorMessage(modelsQuery.error)}
      </Alert>
    );
  }

  const status = modelsQuery.data;

  return (
    <Stack spacing={3}>
      <Stack
        direction={{
          xs: "column",
          md: "row",
        }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{
          xs: "flex-start",
          md: "center",
        }}
      >
        <Box>
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
          >
            <BrainCircuit size={24} />

            <Typography variant="h5">
              Model monitoring
            </Typography>
          </Stack>

          <Typography
            variant="body2"
            color="text.secondary"
            mt={0.5}
          >
            Registry status, deployment readiness and model metadata.
          </Typography>
        </Box>

        <Button
          variant="outlined"
          startIcon={
            modelsQuery.isFetching ? (
              <CircularProgress size={16} />
            ) : (
              <RefreshCw size={16} />
            )
          }
          disabled={modelsQuery.isFetching}
          onClick={() =>
            void modelsQuery.refetch()
          }
        >
          Refresh
        </Button>
      </Stack>

      <Stack
        direction={{
          xs: "column",
          sm: "row",
        }}
        spacing={2}
      >
        <Paper
          variant="outlined"
          sx={{ p: 2.5, flex: 1 }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
          >
            <DatabaseZap size={22} />

            <Box>
              <Typography
                variant="body2"
                color="text.secondary"
              >
                Registered models
              </Typography>

              <Typography variant="h5">
                {registeredModels.length}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{ p: 2.5, flex: 1 }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
          >
            <CheckCircle2
              size={22}
              color="#2e7d32"
            />

            <Box>
              <Typography
                variant="body2"
                color="text.secondary"
              >
                Registry status
              </Typography>

              <Typography variant="h5">
                {registeredModels.length > 0
                  ? "Ready"
                  : "Empty"}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{ p: 2.5, flex: 1 }}
        >
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
          >
            <ShieldCheck size={22} />

            <Box>
              <Typography
                variant="body2"
                color="text.secondary"
              >
                Monitoring
              </Typography>

              <Typography variant="h5">
                Active
              </Typography>
            </Box>
          </Stack>
        </Paper>
      </Stack>

      <Paper variant="outlined" sx={{ p: 3, borderColor: "primary.main", background: "linear-gradient(135deg, rgba(0,124,137,.08), rgba(255,255,255,.96))" }}>
        <Stack direction={{xs:"column",md:"row"}} justifyContent="space-between" gap={2}>
          <Box><Typography variant="overline" color="primary" fontWeight={800}>Nigerian geological knowledge engine</Typography><Typography variant="h6">Niger Delta calibrated continual learning</Typography><Typography variant="body2" color="text.secondary" mt={.5}>Registered models can be retrained with newly validated Nigerian well datasets. Every retraining run must create a new version, preserve the previous model and record validation, leakage and generalisation diagnostics before deployment.</Typography></Box>
          <Stack direction="row" gap={1} flexWrap="wrap"><Chip label="Niger Delta calibrated" color="primary"/><Chip label="Version controlled"/><Chip label="Continual retraining"/><Chip label="Leakage checks"/><Chip label="Overfitting diagnostics"/></Stack>
        </Stack>
      </Paper>

      <Paper
        variant="outlined"
        sx={{ p: 3 }}
      >
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          mb={2}
        >
          <Activity size={20} />

          <Typography variant="h6">
            Registered model names
          </Typography>
        </Stack>

        {registeredModels.length === 0 ? (
          <Alert severity="info">
            No registered models were returned by the backend.
          </Alert>
        ) : (
          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            flexWrap="wrap"
          >
            {registeredModels.map((model: any) => (
              <Chip
                key={model}
                label={model}
                color="primary"
                variant="outlined"
              />
            ))}
          </Stack>
        )}
      </Paper>

      {detailedModels.length > 0 && (
        <Stack spacing={2}>
          <Typography variant="h6">
            Model details
          </Typography>

          {detailedModels.map((model: any, index: number) => (
            <ModelCard
              key={
                typeof model === "object" &&
                model !== null &&
                "id" in model
                  ? String(
                      (model as Record<string, unknown>).id,
                    )
                  : index
              }
              model={model}
              index={index}
            />
          ))}
        </Stack>
      )}

      {status &&
        Object.entries(status)
          .filter(
            ([key]) =>
              !["registered_models", "models"].includes(
                key,
              ),
          )
          .length > 0 && (
          <Paper
            variant="outlined"
            sx={{ p: 3 }}
          >
            <Typography
              variant="h6"
              gutterBottom
            >
              Registry metadata
            </Typography>

            <Stack spacing={1.25}>
              {Object.entries(status)
                .filter(
                  ([key]) =>
                    ![
                      "registered_models",
                      "models",
                    ].includes(key),
                )
                .map(([key, value]) => (
                  <Stack
                    key={key}
                    direction={{
                      xs: "column",
                      sm: "row",
                    }}
                    spacing={1}
                    justifyContent="space-between"
                  >
                    <Typography
                      variant="body2"
                      color="text.secondary"
                    >
                      {formatLabel(key)}
                    </Typography>

                    <Typography variant="body2">
                      {formatValue(value)}
                    </Typography>
                  </Stack>
                ))}
            </Stack>
          </Paper>
        )}
    </Stack>
  );
}
