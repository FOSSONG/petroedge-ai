import { getAccessToken } from "../api/http";

export interface RealtimeEvent<T = Record<string, unknown>> {
  event_type: string;
  channel: string;
  payload: T;
  timestamp?: string;
}

export type RealtimeState =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export interface RealtimeClientOptions {
  channels?: string[];
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  onEvent?: (event: RealtimeEvent) => void;
  onStateChange?: (state: RealtimeState) => void;
}

function buildWebSocketBaseUrl(): string {
  const configured = import.meta.env.VITE_WS_BASE_URL?.replace(/\/+$/, "");

  if (configured) {
    return configured;
  }

  const apiBase =
    import.meta.env.VITE_API_BASE_URL ??
    "http://127.0.0.1:8000/api/v1";

  return apiBase
    .replace(/^http:/, "ws:")
    .replace(/^https:/, "wss:")
    .replace(/\/+$/, "");
}

export class PetroEdgeRealtimeClient {
  private socket: WebSocket | null = null;
  private stopped = false;
  private reconnectTimer: number | null = null;
  private reconnectAttempt = 0;
  private readonly channels = new Set<string>();
  private readonly reconnectDelayMs: number;
  private readonly maxReconnectDelayMs: number;
  private readonly onEvent?: (event: RealtimeEvent) => void;
  private readonly onStateChange?: (state: RealtimeState) => void;

  constructor(options: RealtimeClientOptions = {}) {
    for (const channel of options.channels ?? ["global"]) {
      this.channels.add(channel);
    }

    this.reconnectDelayMs = options.reconnectDelayMs ?? 1000;
    this.maxReconnectDelayMs = options.maxReconnectDelayMs ?? 15000;
    this.onEvent = options.onEvent;
    this.onStateChange = options.onStateChange;
  }

  connect(): void {
    this.stopped = false;
    this.open();
  }

  disconnect(): void {
    this.stopped = true;

    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.socket?.close(1000, "Client disconnected");
    this.socket = null;
    this.onStateChange?.("closed");
  }

  subscribe(...channels: string[]): void {
    for (const channel of channels) {
      this.channels.add(channel);
    }

    this.send({
      action: "subscribe",
      channels,
    });
  }

  unsubscribe(...channels: string[]): void {
    for (const channel of channels) {
      this.channels.delete(channel);
    }

    this.send({
      action: "unsubscribe",
      channels,
    });
  }

  ping(): void {
    this.send({ action: "ping" });
  }

  private open(): void {
    if (
      this.stopped ||
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.onStateChange?.("connecting");

    const url = new URL(`${buildWebSocketBaseUrl()}/realtime/ws`);
    url.searchParams.set(
      "channels",
      Array.from(this.channels).join(","),
    );

    const token = getAccessToken();
    if (token) {
      url.searchParams.set("token", token);
    }

    this.socket = new WebSocket(url.toString());

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStateChange?.("open");
    };

    this.socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as RealtimeEvent;
        this.onEvent?.(event);
      } catch {
        // Ignore malformed events and preserve the live connection.
      }
    };

    this.socket.onerror = () => {
      this.onStateChange?.("error");
    };

    this.socket.onclose = () => {
      this.socket = null;
      this.onStateChange?.("closed");

      if (!this.stopped) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      this.reconnectDelayMs * 2 ** this.reconnectAttempt,
      this.maxReconnectDelayMs,
    );

    this.reconnectAttempt += 1;

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.open();
    }, delay);
  }

  private send(payload: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }
}
