import {
  Chip,
  Tooltip,
} from "@mui/material";

import {
  Activity,
  CircleAlert,
  LoaderCircle,
  WifiOff,
} from "lucide-react";

import {
  useRealtime,
} from "./RealtimeContext";

interface RealtimeStatusProps {
  compact?: boolean;
}

export function RealtimeStatus({
  compact = false,
}: RealtimeStatusProps) {
  const realtime = useRealtime();

  let label = "Offline";

  if (realtime.connected) {
    label =
      realtime.latencyMs === null
        ? "Live"
        : `Live ${realtime.latencyMs} ms`;
  } else if (
    realtime.state === "connecting" ||
    realtime.state === "reconnecting"
  ) {
    label = compact
      ? "Connecting"
      : `Reconnecting (${realtime.reconnectAttempts})`;
  } else if (
    realtime.state === "error"
  ) {
    label = "Realtime error";
  }

  const icon = realtime.connected ? (
    <Activity size={15} />
  ) : realtime.state === "connecting" ||
    realtime.state === "reconnecting" ? (
    <LoaderCircle size={15} />
  ) : realtime.state === "error" ? (
    <CircleAlert size={15} />
  ) : (
    <WifiOff size={15} />
  );

  return (
    <Tooltip
      title={
        realtime.lastError ??
        `${realtime.channels.length} subscribed channels`
      }
    >
      <Chip
        icon={icon}
        label={label}
        size="small"
        color={
          realtime.connected
            ? "success"
            : realtime.state === "error"
              ? "error"
              : "default"
        }
        variant={
          realtime.connected
            ? "filled"
            : "outlined"
        }
      />
    </Tooltip>
  );
}