import { useEffect, useRef, useState } from "react";
import { Alert, Box, CircularProgress, Stack, Typography } from "@mui/material";

interface Props { data: unknown[]; layout: Record<string, unknown>; config?: Record<string, unknown>; minHeight?: number; }

type PlotlyApi = {
  react: (element: HTMLDivElement, data: unknown[], layout: object, config: object) => Promise<void>;
  purge: (element: HTMLDivElement) => void;
  Plots?: { resize: (element: HTMLDivElement) => void };
};

let plotlyPromise: Promise<PlotlyApi> | null = null;
function loadPlotly(): Promise<PlotlyApi> {
  if (!plotlyPromise) {
    plotlyPromise = import("plotly.js-dist-min").then((module) =>
      ((module as unknown as { default?: PlotlyApi }).default ?? module) as unknown as PlotlyApi,
    );
  }
  return plotlyPromise;
}

const DEFAULT_CONFIG: Record<string, unknown> = {};

export function SafePlot({ data, layout, config = DEFAULT_CONFIG, minHeight = 620 }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let active = true;
    let api: PlotlyApi | null = null;
    setState("loading");
    setMessage("");

    loadPlotly()
      .then(async (loaded) => {
        if (!active) return;
        api = loaded;
        await loaded.react(element, data, layout, { responsive: true, displaylogo: false, scrollZoom: true, ...config });
        if (active) setState("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setMessage(error instanceof Error ? error.message : "The chart engine could not render this plot.");
        setState("error");
      });

    const resize = () => { if (api?.Plots?.resize && ref.current) api.Plots.resize(ref.current); };
    window.addEventListener("resize", resize);
    return () => {
      active = false;
      window.removeEventListener("resize", resize);
      if (api && element) api.purge(element);
    };
  }, [data, layout, config]);


  return <Box sx={{ position: "relative", minHeight }}>
    {state === "error" && <Alert severity="error">Interactive chart unavailable: {message}</Alert>}
    {state === "loading" && <Stack alignItems="center" justifyContent="center" sx={{ position: "absolute", inset: 0, zIndex: 1 }}><CircularProgress size={28}/><Typography variant="body2" color="text.secondary" mt={1}>Loading interactive chart…</Typography></Stack>}
    <Box ref={ref} sx={{ width: "100%", minHeight, visibility: "visible" }}/>
  </Box>;
}
