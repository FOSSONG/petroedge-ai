import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Database,
  FileBarChart,
  Gauge,
  Radio,
  RefreshCw,
  Trash2,
  Workflow,
} from "lucide-react";

import { useRealtime } from "./RealtimeContext";
import type { RealtimeEvent } from "./eventTypes";

function formatTime(value?: string): string {
  if (!value) return "Just now";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function titleCase(value: string): string {
  return value
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function readableValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(readableValue).join(", ");
  return "Available";
}

function eventPresentation(event: RealtimeEvent) {
  const type = event.event_type.toLowerCase();

  if (type.includes("alert") || type.includes("failed") || type.includes("error")) {
    return {
      title: type.includes("alert") ? "Operational alert" : "Process exception",
      colour: "error" as const,
      icon: <AlertTriangle size={20} />,
    };
  }

  if (type.includes("dataset") || type.includes("upload") || type.includes("ingest")) {
    return {
      title: "Dataset activity",
      colour: "info" as const,
      icon: <Database size={20} />,
    };
  }

  if (type.includes("prediction") || type.includes("model") || type.includes("inference")) {
    return {
      title: "AI model activity",
      colour: "secondary" as const,
      icon: <Bot size={20} />,
    };
  }

  if (type.includes("report")) {
    return {
      title: "Report activity",
      colour: "success" as const,
      icon: <FileBarChart size={20} />,
    };
  }

  if (type.includes("job") || type.includes("workflow")) {
    return {
      title: "Workflow activity",
      colour: "warning" as const,
      icon: <Workflow size={20} />,
    };
  }

  if (type.includes("stream") || type.includes("sample")) {
    return {
      title: "Live well stream",
      colour: "primary" as const,
      icon: <Gauge size={20} />,
    };
  }

  if (type.includes("completed") || type.includes("ready")) {
    return {
      title: "Process completed",
      colour: "success" as const,
      icon: <CheckCircle2 size={20} />,
    };
  }

  return {
    title: "Platform activity",
    colour: "default" as const,
    icon: <Activity size={20} />,
  };
}

function eventFields(event: RealtimeEvent): Array<[string, unknown]> {
  const preferredKeys = [
    "well_id",
    "dataset_id",
    "dataset_name",
    "job_id",
    "model_name",
    "model_id",
    "status",
    "progress",
    "message",
    "pay_intervals",
    "top_depth",
    "bottom_depth",
    "records_processed",
    "latency_ms",
  ];

  const fields: Array<[string, unknown]> = [];
  const used = new Set<string>();

  for (const key of preferredKeys) {
    if (key in event.payload) {
      fields.push([key, event.payload[key]]);
      used.add(key);
    }
  }

  for (const [key, value] of Object.entries(event.payload)) {
    if (used.has(key) || typeof value === "object") continue;
    fields.push([key, value]);
    if (fields.length >= 8) break;
  }

  return fields;
}

function EventCard({ event }: { event: RealtimeEvent }) {
  const presentation = eventPresentation(event);
  const fields = eventFields(event);
  const progressValue = Number(event.payload.progress);
  const hasProgress = Number.isFinite(progressValue) && progressValue >= 0;

  return (
    <Paper variant="outlined" sx={{ p: 2.25 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-start" }}>
        <Box
          sx={{
            width: 42,
            height: 42,
            display: "grid",
            placeItems: "center",
            borderRadius: 2,
            bgcolor: "action.hover",
            color: `${presentation.colour}.main`,
            flexShrink: 0,
          }}
        >
          {presentation.icon}
        </Box>

        <Box flex={1} minWidth={0}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1}>
            <Box>
              <Typography fontWeight={700}>{presentation.title}</Typography>
              <Typography variant="body2" color="text.secondary">
                {titleCase(event.event_type)}
              </Typography>
            </Box>

            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Chip size="small" label={titleCase(event.channel)} color={presentation.colour} variant="outlined" />
              <Typography variant="caption" color="text.secondary">
                {formatTime(event.occurred_at)}
              </Typography>
            </Stack>
          </Stack>

          {hasProgress && (
            <Box mt={1.5}>
              <Stack direction="row" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Progress</Typography>
                <Typography variant="caption" fontWeight={700}>{Math.min(progressValue, 100)}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={Math.min(progressValue, 100)} />
            </Box>
          )}

          {fields.length > 0 && (
            <Grid container spacing={1.25} mt={0.5}>
              {fields.map(([key, value]) => (
                <Grid item xs={12} sm={6} md={4} key={key}>
                  <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: "action.hover", height: "100%" }}>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {titleCase(key)}
                    </Typography>
                    <Typography variant="body2" fontWeight={650} noWrap title={readableValue(value)}>
                      {readableValue(value)}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      </Stack>
    </Paper>
  );
}

export function RealtimeEventFeed() {
  const realtime = useRealtime();

  return (
    <Stack spacing={2.5}>
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={2} alignItems={{ sm: "center" }}>
          <Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <Radio size={22} />
              <Typography variant="h5">Live platform events</Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              Real-time dataset, workflow, model, alert and reporting activity from the PetroEdge backend.
            </Typography>
          </Box>

          <Stack direction="row" spacing={1} alignItems="center">
            <Chip
              label={realtime.connected ? "Connected" : titleCase(realtime.state)}
              color={realtime.connected ? "success" : realtime.state === "error" ? "error" : "default"}
              size="small"
            />
            <Chip label={`${realtime.events.length} events`} size="small" variant="outlined" />
            <Button
              variant="outlined"
              startIcon={<RefreshCw size={17} />}
              disabled={realtime.connected}
              onClick={realtime.reconnect}
            >
              Reconnect
            </Button>
            <Button
              variant="outlined"
              startIcon={<Trash2 size={17} />}
              disabled={realtime.events.length === 0}
              onClick={realtime.clearEvents}
            >
              Clear
            </Button>
          </Stack>
        </Stack>
      </Paper>

      {realtime.lastError && <Alert severity="warning">{realtime.lastError}</Alert>}

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} divider={<Divider flexItem orientation="vertical" />}>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">Connection</Typography>
            <Typography fontWeight={700}>{realtime.connected ? "Live" : titleCase(realtime.state)}</Typography>
          </Box>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">Subscribed channels</Typography>
            <Typography fontWeight={700}>{realtime.channels.length || 0}</Typography>
          </Box>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">Latency</Typography>
            <Typography fontWeight={700}>{realtime.latencyMs === null ? "—" : `${realtime.latencyMs} ms`}</Typography>
          </Box>
          <Box flex={1}>
            <Typography variant="caption" color="text.secondary">Buffered events</Typography>
            <Typography fontWeight={700}>{realtime.events.length}</Typography>
          </Box>
        </Stack>
      </Paper>

      {realtime.events.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
          <Radio size={34} />
          <Typography variant="h6" mt={1.5}>Waiting for platform activity</Typography>
          <Typography color="text.secondary" mt={0.5}>
            New uploads, workflows, predictions, alerts and reports will appear here automatically.
          </Typography>
        </Paper>
      ) : (
        <Stack spacing={1.5}>
          {realtime.events.map((event, index) => (
            <EventCard key={event.event_id ?? `${event.event_type}-${event.occurred_at ?? index}`} event={event} />
          ))}
        </Stack>
      )}
    </Stack>
  );
}
