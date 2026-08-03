import { useMemo, useState } from "react";
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
  Typography,
} from "@mui/material";

import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

import { fetchAlerts } from "../../api/client";
import { ApiError } from "../../api/http";
import type { AlertRecord } from "../../api/types";

type ChipColour =
  | "default"
  | "primary"
  | "secondary"
  | "error"
  | "info"
  | "success"
  | "warning";

function normalise(value?: string | null): string {
  return value?.trim().toLowerCase() || "unknown";
}

function severityColour(severity?: string): ChipColour {
  switch (normalise(severity)) {
    case "critical":
    case "high":
    case "error":
      return "error";

    case "medium":
    case "warning":
      return "warning";

    case "low":
    case "info":
      return "info";

    default:
      return "default";
  }
}

function statusColour(status?: string): ChipColour {
  switch (normalise(status)) {
    case "resolved":
    case "closed":
    case "acknowledged":
      return "success";

    case "active":
    case "open":
    case "triggered":
      return "error";

    case "investigating":
    case "pending":
      return "warning";

    default:
      return "default";
  }
}

function formatDate(value?: string): string {
  if (!value) {
    return "Time unavailable";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return (
        "The alert service cannot be reached. " +
        "Confirm that the FastAPI backend is running."
      );
    }

    if (error.status === 401) {
      return "Your session has expired.";
    }

    if (error.status === 403) {
      return "Your account cannot access operational alerts.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Operational alerts could not be loaded.";
}

interface SummaryCardProps {
  label: string;
  value: number;
  icon: React.ReactNode;
}

function SummaryCard({
  label,
  value,
  icon,
}: SummaryCardProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2.5,
        minWidth: 180,
        flex: 1,
      }}
    >
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
      >
        {icon}

        <Box>
          <Typography
            variant="body2"
            color="text.secondary"
          >
            {label}
          </Typography>

          <Typography variant="h5">
            {value.toLocaleString()}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

export function AlertsPanel() {
  const [severityFilter, setSeverityFilter] =
    useState("all");

  const [statusFilter, setStatusFilter] =
    useState("all");

  const alertsQuery = useQuery<AlertRecord[]>({
    queryKey: ["alerts"],
    queryFn: fetchAlerts,
    staleTime: 10_000,
    refetchInterval: 15_000,
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

  const alerts = useMemo<AlertRecord[]>(() => {
    const response = alertsQuery.data as unknown;

    if (Array.isArray(response)) {
      return response;
    }

    if (
      response &&
      typeof response === "object"
    ) {
      const record = response as Record<string, unknown>;

      const possibleCollections = [
        record.alerts,
        record.items,
        record.results,
        record.data,
      ];

      for (const collection of possibleCollections) {
        if (Array.isArray(collection)) {
          return collection as AlertRecord[];
        }
      }
    }

    return [];
  }, [alertsQuery.data]);

  const severities = useMemo(
    () =>
      Array.from(
        new Set(
          alerts.map((alert) =>
            normalise(alert.severity),
          ),
        ),
      ).sort(),
    [alerts],
  );

  const statuses = useMemo(
    () =>
      Array.from(
        new Set(
          alerts.map((alert) =>
            normalise(alert.status),
          ),
        ),
      ).sort(),
    [alerts],
  );

  const filteredAlerts = useMemo(
    () =>
      [...alerts]
        .filter((alert) => {
          const severityMatches =
            severityFilter === "all" ||
            normalise(alert.severity) ===
              severityFilter;

          const statusMatches =
            statusFilter === "all" ||
            normalise(alert.status) ===
              statusFilter;

          return severityMatches && statusMatches;
        })
        .sort((left, right) => {
          const leftTime = left.created_at
            ? new Date(left.created_at).getTime()
            : 0;

          const rightTime = right.created_at
            ? new Date(right.created_at).getTime()
            : 0;

          return rightTime - leftTime;
        }),
    [alerts, severityFilter, statusFilter],
  );

  const criticalCount = alerts.filter((alert) =>
    ["critical", "high", "error"].includes(
      normalise(alert.severity),
    ),
  ).length;

  const activeCount = alerts.filter((alert) =>
    ["active", "open", "triggered"].includes(
      normalise(alert.status),
    ),
  ).length;

  const resolvedCount = alerts.filter((alert) =>
    ["resolved", "closed", "acknowledged"].includes(
      normalise(alert.status),
    ),
  ).length;

  if (alertsQuery.isLoading) {
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
            Loading operational alerts...
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (alertsQuery.isError) {
    return (
      <Alert
        severity="error"
        action={
          <Button
            color="inherit"
            size="small"
            onClick={() =>
              void alertsQuery.refetch()
            }
          >
            Retry
          </Button>
        }
      >
        {errorMessage(alertsQuery.error)}
      </Alert>
    );
  }

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
            <Bell size={24} />

            <Typography variant="h5">
              Operational alerts
            </Typography>
          </Stack>

          <Typography
            variant="body2"
            color="text.secondary"
            mt={0.5}
          >
            Live drilling, data-quality and model alerts.
          </Typography>
        </Box>

        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
        >
          <Chip
            label={
              alertsQuery.isFetching
                ? "Refreshing"
                : "Live monitoring"
            }
            color={
              alertsQuery.isFetching
                ? "default"
                : "success"
            }
            size="small"
          />

          <Button
            variant="outlined"
            startIcon={
              alertsQuery.isFetching ? (
                <CircularProgress size={16} />
              ) : (
                <RefreshCw size={16} />
              )
            }
            disabled={alertsQuery.isFetching}
            onClick={() =>
              void alertsQuery.refetch()
            }
          >
            Refresh
          </Button>
        </Stack>
      </Stack>

      <Stack
        direction={{
          xs: "column",
          sm: "row",
        }}
        spacing={2}
      >
        <SummaryCard
          label="Total alerts"
          value={alerts.length}
          icon={<Bell size={22} />}
        />

        <SummaryCard
          label="Critical or high"
          value={criticalCount}
          icon={
            <ShieldAlert
              size={22}
              color="#d32f2f"
            />
          }
        />

        <SummaryCard
          label="Active"
          value={activeCount}
          icon={
            <AlertTriangle
              size={22}
              color="#ed6c02"
            />
          }
        />

        <SummaryCard
          label="Resolved"
          value={resolvedCount}
          icon={
            <CheckCircle2
              size={22}
              color="#2e7d32"
            />
          }
        />
      </Stack>

      <Paper
        variant="outlined"
        sx={{ p: 2 }}
      >
        <Stack
          direction={{
            xs: "column",
            sm: "row",
          }}
          spacing={2}
        >
          <FormControl
            size="small"
            sx={{ minWidth: 180 }}
          >
            <InputLabel id="severity-filter-label">
              Severity
            </InputLabel>

            <Select
              labelId="severity-filter-label"
              value={severityFilter}
              label="Severity"
              onChange={(event) =>
                setSeverityFilter(event.target.value)
              }
            >
              <MenuItem value="all">
                All severities
              </MenuItem>

              {severities.map((severity) => (
                <MenuItem
                  key={severity}
                  value={severity}
                >
                  {severity}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl
            size="small"
            sx={{ minWidth: 180 }}
          >
            <InputLabel id="status-filter-label">
              Status
            </InputLabel>

            <Select
              labelId="status-filter-label"
              value={statusFilter}
              label="Status"
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
            >
              <MenuItem value="all">
                All statuses
              </MenuItem>

              {statuses.map((status) => (
                <MenuItem
                  key={status}
                  value={status}
                >
                  {status}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box flex={1} />

          <Typography
            variant="body2"
            color="text.secondary"
            alignSelf="center"
          >
            Showing {filteredAlerts.length} of{" "}
            {alerts.length}
          </Typography>
        </Stack>
      </Paper>

      {filteredAlerts.length === 0 ? (
        <Alert severity="info">
          No alerts match the selected filters.
        </Alert>
      ) : (
        <Stack spacing={1.5}>
          {filteredAlerts.map((alert) => (
            <Paper
              key={alert.id}
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
                <Box flex={1}>
                  <Stack
                    direction="row"
                    spacing={1}
                    flexWrap="wrap"
                    mb={1}
                  >
                    <Chip
                      label={
                        alert.severity || "unknown"
                      }
                      color={severityColour(
                        alert.severity,
                      )}
                      size="small"
                    />

                    <Chip
                      label={
                        alert.status || "unknown"
                      }
                      color={statusColour(
                        alert.status,
                      )}
                      variant="outlined"
                      size="small"
                    />

                    {alert.well_id && (
                      <Chip
                        label={alert.well_id}
                        variant="outlined"
                        size="small"
                      />
                    )}
                  </Stack>

                  <Typography variant="body1">
                    {alert.message}
                  </Typography>

                  <Typography
                    variant="caption"
                    color="text.secondary"
                  >
                    {formatDate(alert.created_at)}
                  </Typography>
                </Box>

                <Typography
                  variant="caption"
                  color="text.secondary"
                >
                  ID: {alert.id}
                </Typography>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

