export type RealtimeConnectionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

export interface RealtimeEvent {
  event_type: string;
  channel: string;
  payload: Record<string, unknown>;
  event_id?: string;
  occurred_at?: string;
  correlation_id?: string | null;
  actor_id?: string | null;
}

export interface RealtimeSnapshot {
  state: RealtimeConnectionState;
  connected: boolean;
  reconnectAttempts: number;
  channels: string[];
  clientId: string | null;
  latencyMs: number | null;
  lastEvent: RealtimeEvent | null;
  lastError: string | null;
}