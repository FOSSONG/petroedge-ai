import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import { Alert, Box, CircularProgress, Stack, Typography } from "@mui/material";

interface SafePlotProps {
  data?: unknown[];
  layout?: Record<string, unknown>;
  config?: Record<string, unknown>;
  style?: CSSProperties;
  className?: string;
  useResizeHandler?: boolean;
}

type PlotlyModule = {
  newPlot: (node: HTMLElement, data: unknown[], layout?: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown> | unknown;
  react: (node: HTMLElement, data: unknown[], layout?: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown> | unknown;
  purge: (node: HTMLElement) => void;
  Plots?: { resize: (node: HTMLElement) => void };
};

let plotlyPromise: Promise<PlotlyModule> | null = null;

function loadPlotly(): Promise<PlotlyModule> {
  if (!plotlyPromise) {
    plotlyPromise = import("plotly.js-dist-min").then((module) => {
      const candidate = (module.default ?? module) as unknown as PlotlyModule;
      if (!candidate || typeof candidate.newPlot !== "function" || typeof candidate.react !== "function") {
        throw new Error("The Plotly chart engine did not expose the expected browser API.");
      }
      return candidate;
    });
  }
  return plotlyPromise;
}

export function SafePlot({ data = [], layout = {}, config = {}, style, className, useResizeHandler = true }: SafePlotProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const plotlyRef = useRef<PlotlyModule | null>(null);
  const renderedRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const instanceId = useId();

  useEffect(() => {
    let active = true;
    const host = hostRef.current;
    if (!host) return;

    setLoading(true);
    setError(null);

    loadPlotly()
      .then(async (Plotly) => {
        if (!active || !hostRef.current) return;
        plotlyRef.current = Plotly;
        const safeData = Array.isArray(data) ? data : [];
        const safeLayout = { autosize: true, ...layout };
        const safeConfig = { responsive: true, displaylogo: false, ...config };
        if (renderedRef.current) await Plotly.react(hostRef.current, safeData, safeLayout, safeConfig);
        else {
          await Plotly.newPlot(hostRef.current, safeData, safeLayout, safeConfig);
          renderedRef.current = true;
        }
        if (active) setLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setLoading(false);
        setError(reason instanceof Error ? reason.message : "Interactive chart engine failed to load.");
      });

    return () => { active = false; };
  }, [data, layout, config, instanceId]);

  useEffect(() => {
    if (!useResizeHandler || typeof ResizeObserver === "undefined") return;
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(() => {
      if (plotlyRef.current?.Plots?.resize && hostRef.current) {
        try { plotlyRef.current.Plots.resize(hostRef.current); } catch { /* chart remains usable */ }
      }
    });
    observer.observe(host);
    return () => observer.disconnect();
  }, [useResizeHandler]);

  useEffect(() => () => {
    if (hostRef.current && plotlyRef.current && renderedRef.current) {
      try { plotlyRef.current.purge(hostRef.current); } catch { /* no-op */ }
    }
  }, []);

  if (error) return <Alert severity="error" sx={{ minHeight: 96, alignItems: "center" }}>Interactive chart unavailable: {error}</Alert>;

  return (
    <Box position="relative" width="100%" height="100%" minHeight={240} className={className} sx={style}>
      {loading && <Box position="absolute" inset={0} display="grid" zIndex={2} sx={{ placeItems: "center", bgcolor: "background.paper" }}><Stack alignItems="center" spacing={1}><CircularProgress size={28}/><Typography variant="body2" color="text.secondary">Loading interactive chart…</Typography></Stack></Box>}
      <Box ref={hostRef} width="100%" height="100%" minHeight={240} aria-label="Interactive PetroEdge chart" />
    </Box>
  );
}
