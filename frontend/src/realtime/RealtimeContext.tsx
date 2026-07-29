import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";


import { getAccessToken } from "../api/http";
import type {
  RealtimeEvent,
  RealtimeSnapshot,
} from "./eventTypes";

interface RealtimeContextValue extends RealtimeSnapshot {
  events: RealtimeEvent[];
  subscribe: (channels: string[]) => void;
  unsubscribe: (channels: string[]) => void;
  reconnect: () => void;
  clearEvents: () => void;
}

interface RealtimeProviderProps extends PropsWithChildren {
  userId?: string;
  initialChannels?: string[];
  maximumEvents?: number;
}

const initialSnapshot: RealtimeSnapshot = {
  state: "idle",
  connected: false,
  reconnectAttempts: 0,
  channels: [],
  clientId: null,
  latencyMs: null,
  lastEvent: null,
  lastError: null,
};

const RealtimeContext =
  createContext<RealtimeContextValue | undefined>(
    undefined,
  );

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function normaliseEvent(
  value: unknown,
): RealtimeEvent | null {
  if (!isRecord(value)) {
    return null;
  }

  if (typeof value.event_type !== "string") {
    return null;
  }

  return {
    event_type: value.event_type,
    channel:
      typeof value.channel === "string"
        ? value.channel
        : "global",
    payload: isRecord(value.payload)
      ? value.payload
      : {},
    event_id:
      typeof value.event_id === "string"
        ? value.event_id
        : undefined,
    occurred_at:
      typeof value.occurred_at === "string"
        ? value.occurred_at
        : undefined,
    correlation_id:
      typeof value.correlation_id === "string"
        ? value.correlation_id
        : null,
    actor_id:
      typeof value.actor_id === "string"
        ? value.actor_id
        : null,
  };
}

function deriveWebSocketUrl(): string {
  const apiBase =
    import.meta.env.VITE_API_BASE_URL ??
    "http://127.0.0.1:8000/api/v1";

  return (
    apiBase
      .replace(/\/+$/, "")
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:") +
    "/realtime/ws"
  );
}

export function RealtimeProvider({
  children,
  userId,
  initialChannels = [
    "global",
    "alerts",
    "jobs",
    "models",
    "wells",
  ],
  maximumEvents = 200,
}: RealtimeProviderProps) {
  const socketRef =
    useRef<WebSocket | null>(null);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  const heartbeatTimerRef =
    useRef<ReturnType<typeof setInterval> | null>(
      null,
    );

  const manualCloseRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const pingStartedAtRef = useRef<number | null>(null);

  const channelsRef = useRef(
    new Set(initialChannels),
  );

  const [snapshot, setSnapshot] =
    useState<RealtimeSnapshot>({
      ...initialSnapshot,
      channels: initialChannels,
    });

  const [events, setEvents] =
    useState<RealtimeEvent[]>([]);

  const updateSnapshot = useCallback(
    (
      updates: Partial<RealtimeSnapshot>,
    ) => {
      setSnapshot((current) => ({
        ...current,
        ...updates,
      }));
    },
    [],
  );

  const stopHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const connectRef =
    useRef<() => void>(() => undefined);

  const send = useCallback(
    (
      message: Record<string, unknown>,
    ): boolean => {
      const socket = socketRef.current;

      if (
        !socket ||
        socket.readyState !== WebSocket.OPEN
      ) {
        return false;
      }

      socket.send(JSON.stringify(message));
      return true;
    },
    [],
  );

  const scheduleReconnect = useCallback(() => {
    if (manualCloseRef.current) {
      return;
    }

    reconnectAttemptsRef.current += 1;

    const attempt =
      reconnectAttemptsRef.current;

    const delay = Math.min(
      30_000,
      1_000 * 2 ** Math.min(attempt - 1, 5),
    );

    updateSnapshot({
      state: "reconnecting",
      connected: false,
      reconnectAttempts: attempt,
    });

    reconnectTimerRef.current = setTimeout(
      () => {
        connectRef.current();
      },
      delay,
    );
  }, [updateSnapshot]);

  const connect = useCallback(() => {
    const existingSocket = socketRef.current;

    if (
      existingSocket?.readyState ===
        WebSocket.OPEN ||
      existingSocket?.readyState ===
        WebSocket.CONNECTING
    ) {
      return;
    }

    manualCloseRef.current = false;

    const configuredUrl =
      import.meta.env.VITE_REALTIME_WS_URL ??
      deriveWebSocketUrl();

    const url = new URL(configuredUrl, window.location.origin);

    url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    url.searchParams.set(
      "channels",
      [...channelsRef.current].join(","),
    );

    updateSnapshot({
      state:
        reconnectAttemptsRef.current > 0
          ? "reconnecting"
          : "connecting",
      lastError: null,
    });

    const token = getAccessToken();

    if (!token) {
      manualCloseRef.current = true;

      updateSnapshot({
        state: "disconnected",
        connected: false,
        clientId: null,
        lastError:
          "Realtime authentication requires a valid login session.",
      });

      return;
    }

    const socket = new WebSocket(
      url.toString(),
      ["petroedge", token],
    );

    socketRef.current = socket;

    socket.addEventListener("open", () => {
      reconnectAttemptsRef.current = 0;

      updateSnapshot({
        state: "connected",
        connected: true,
        reconnectAttempts: 0,
        lastError: null,
      });

      stopHeartbeat();

      heartbeatTimerRef.current =
        setInterval(() => {
          pingStartedAtRef.current =
            Date.now();

          send({
            action: "ping",
          });
        }, 20_000);
    });

    socket.addEventListener(
      "message",
      (message) => {
        let parsed: unknown;

        try {
          parsed = JSON.parse(
            String(message.data),
          );
        } catch {
          return;
        }

        const event =
          normaliseEvent(parsed);

        if (!event) {
          return;
        }

        if (
          event.event_type ===
          "connection.ready"
        ) {
          const clientId =
            typeof event.payload.client_id ===
            "string"
              ? event.payload.client_id
              : null;

          const channels =
            Array.isArray(
              event.payload.channels,
            )
              ? event.payload.channels.filter(
                  (
                    channel,
                  ): channel is string =>
                    typeof channel === "string",
                )
              : [...channelsRef.current];

          channelsRef.current =
            new Set(channels);

          updateSnapshot({
            clientId,
            channels,
          });
        }

        if (
          event.event_type ===
          "connection.channels_updated"
        ) {
          const channels =
            Array.isArray(
              event.payload.channels,
            )
              ? event.payload.channels.filter(
                  (
                    channel,
                  ): channel is string =>
                    typeof channel === "string",
                )
              : [];

          channelsRef.current =
            new Set(channels);

          updateSnapshot({
            channels,
          });
        }

        if (
          event.event_type ===
          "connection.pong"
        ) {
          const startedAt =
            pingStartedAtRef.current;

          updateSnapshot({
            latencyMs:
              startedAt === null
                ? null
                : Date.now() - startedAt,
          });

          pingStartedAtRef.current = null;
        }

        if (
          event.event_type ===
          "connection.error"
        ) {
          updateSnapshot({
            lastError:
              typeof event.payload.message ===
              "string"
                ? event.payload.message
                : "Realtime server error.",
          });
        }

        updateSnapshot({
          lastEvent: event,
        });

        setEvents((current) =>
          [event, ...current].slice(
            0,
            maximumEvents,
          ),
        );
      },
    );

    socket.addEventListener(
      "error",
      () => {
        updateSnapshot({
          state: "error",
          lastError:
            "The realtime connection encountered an error.",
        });
      },
    );

    socket.addEventListener(
      "close",
      (event) => {
        socketRef.current = null;
        stopHeartbeat();

        const authenticationFailure =
          event.code === 4401 ||
          event.code === 4403;

        if (authenticationFailure) {
          manualCloseRef.current = true;
        }

        updateSnapshot({
          connected: false,
          clientId: null,
          state:
            manualCloseRef.current ||
            authenticationFailure
              ? "disconnected"
              : "reconnecting",
          lastError:
            authenticationFailure
              ? event.reason ||
                "Realtime authentication failed. Sign in again."
              : manualCloseRef.current
                ? null
                : event.reason ||
                  `WebSocket closed with code ${event.code}.`,
        });

        if (
          !manualCloseRef.current &&
          !authenticationFailure
        ) {
          scheduleReconnect();
        }
      },
    );
  }, [
    maximumEvents,
    scheduleReconnect,
    send,
    stopHeartbeat,
    updateSnapshot,
    userId,
  ]);

  connectRef.current = connect;

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;

    if (reconnectTimerRef.current) {
      clearTimeout(
        reconnectTimerRef.current,
      );

      reconnectTimerRef.current = null;
    }

    stopHeartbeat();

    const socket = socketRef.current;
    socketRef.current = null;

    if (
      socket &&
      socket.readyState !== WebSocket.CLOSED
    ) {
      socket.close(
        1000,
        "Client disconnected",
      );
    }

    updateSnapshot({
      state: "disconnected",
      connected: false,
      clientId: null,
    });
  }, [stopHeartbeat, updateSnapshot]);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  const subscribe = useCallback(
    (channels: string[]) => {
      const validChannels =
        channels.filter(Boolean);

      for (const channel of validChannels) {
        channelsRef.current.add(channel);
      }

      updateSnapshot({
        channels: [...channelsRef.current],
      });

      send({
        action: "subscribe",
        channels: validChannels,
      });
    },
    [send, updateSnapshot],
  );

  const unsubscribe = useCallback(
    (channels: string[]) => {
      const validChannels =
        channels.filter(Boolean);

      for (const channel of validChannels) {
        channelsRef.current.delete(channel);
      }

      if (channelsRef.current.size === 0) {
        channelsRef.current.add("global");
      }

      updateSnapshot({
        channels: [...channelsRef.current],
      });

      send({
        action: "unsubscribe",
        channels: validChannels,
      });
    },
    [send, updateSnapshot],
  );

  const reconnect = useCallback(() => {
    disconnect();

    window.setTimeout(() => {
      manualCloseRef.current = false;
      connect();
    }, 100);
  }, [connect, disconnect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const value =
    useMemo<RealtimeContextValue>(
      () => ({
        ...snapshot,
        events,
        subscribe,
        unsubscribe,
        reconnect,
        clearEvents,
      }),
      [
        snapshot,
        events,
        subscribe,
        unsubscribe,
        reconnect,
        clearEvents,
      ],
    );

  return (
    <RealtimeContext.Provider
      value={value}
    >
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime():
  RealtimeContextValue {
  const context =
    useContext(RealtimeContext);

  if (!context) {
    throw new Error(
      "useRealtime must be used inside RealtimeProvider.",
    );
  }

  return context;
}