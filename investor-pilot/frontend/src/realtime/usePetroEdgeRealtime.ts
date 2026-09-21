import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  PetroEdgeRealtimeClient,
  type RealtimeEvent,
  type RealtimeState,
} from "./client";

export interface UseRealtimeOptions {
  channels?: string[];
  enabled?: boolean;
  onEvent?: (event: RealtimeEvent) => void;
}

export function usePetroEdgeRealtime(
  options: UseRealtimeOptions = {},
) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<RealtimeState>("idle");

  const channelsKey = (options.channels ?? ["global"]).join(",");

  const client = useMemo(
    () =>
      new PetroEdgeRealtimeClient({
        channels: options.channels ?? ["global"],
        onStateChange: setState,
        onEvent: (event) => {
          switch (event.event_type) {
            case "alert.created":
            case "alert.updated":
              void queryClient.invalidateQueries({
                queryKey: ["alerts"],
              });
              break;

            case "job.queued":
            case "job.started":
            case "job.progress":
            case "job.completed":
            case "job.failed":
              void queryClient.invalidateQueries({
                queryKey: ["jobs"],
              });

              if (
                typeof event.payload === "object" &&
                event.payload !== null &&
                "job_id" in event.payload
              ) {
                void queryClient.invalidateQueries({
                  queryKey: [
                    "job",
                    String(
                      (event.payload as { job_id: unknown }).job_id,
                    ),
                  ],
                });
              }
              break;

            case "prediction.completed":
            case "stream.sample":
              void queryClient.invalidateQueries({
                queryKey: ["logs"],
              });
              void queryClient.invalidateQueries({
                queryKey: ["dashboard"],
              });
              break;
          }

          options.onEvent?.(event);
        },
      }),
    [channelsKey, queryClient],
  );

  useEffect(() => {
    if (options.enabled === false) {
      return;
    }

    client.connect();
    return () => client.disconnect();
  }, [client, options.enabled]);

  return {
    state,
    client,
    connected: state === "open",
  };
}
