import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { RefreshCw, Search } from "lucide-react";
import { ApiError } from "../../api/http";
import {
  asRecords,
  fetchResource,
  recordStatus,
  recordTitle,
  type JsonRecord,
  type ResourceDescriptor,
} from "./operationsApi";

interface Props {
  resource: ResourceDescriptor;
  detailPath?: (record: JsonRecord) => string | null;
  actions?: React.ReactNode;
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function statusColour(status?: string): "default" | "success" | "warning" | "error" | "info" {
  const value = status?.toLowerCase() ?? "";
  if (["healthy", "active", "ready", "running", "completed", "loaded", "enabled", "online"].some((item) => value.includes(item))) return "success";
  if (["pending", "queued", "warning", "degraded", "training"].some((item) => value.includes(item))) return "warning";
  if (["failed", "error", "offline", "inactive", "disabled", "critical"].some((item) => value.includes(item))) return "error";
  return status ? "info" : "default";
}

export function ResourcePanel({ resource, detailPath, actions }: Props) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<JsonRecord | null>(null);
  const [detail, setDetail] = useState<unknown>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  const query = useQuery({
    queryKey: ["resource", resource.key, resource.path],
    queryFn: () => fetchResource(resource.path),
    retry: 1,
  });

  const records = useMemo(() => {
    const normalized = asRecords(query.data);
    const term = search.trim().toLowerCase();
    if (!term) return normalized;
    return normalized.filter((record) => pretty(record).toLowerCase().includes(term));
  }, [query.data, search]);

  async function openRecord(record: JsonRecord): Promise<void> {
    setSelected(record);
    setDetail(record);
    setDetailError("");
    const path = detailPath?.(record);
    if (!path) return;

    setDetailLoading(true);
    try {
      setDetail(await fetchResource(path));
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Unable to load details.");
    } finally {
      setDetailLoading(false);
    }
  }

  const errorMessage = query.error instanceof ApiError
    ? query.error.message
    : query.error instanceof Error
      ? query.error.message
      : "Unable to load this resource.";

  return (
    <Stack spacing={2.5}>
      <Card className="feature-hero" variant="outlined">
        <CardContent sx={{ p: { xs: 2.5, md: 3.5 }, position: "relative", zIndex: 1 }}>
          <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
            <Box>
              <Typography variant="h4">{resource.label}</Typography>
              <Typography sx={{ mt: 1, maxWidth: 760, opacity: 0.92 }}>{resource.description}</Typography>
            </Box>
            <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
              <Chip className="hero-chip" label={`${records.length} visible`} />
              <Button
                variant="contained"
                color="secondary"
                startIcon={<RefreshCw size={17} />}
                onClick={() => void query.refetch()}
              >
                Refresh
              </Button>
              {actions}
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      <TextField
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder={`Search ${resource.label.toLowerCase()}...`}
        InputProps={{ startAdornment: <Search size={18} style={{ marginRight: 10 }} /> }}
        fullWidth
      />

      {query.isLoading && <Box display="grid" sx={{ placeItems: "center", minHeight: 220 }}><CircularProgress /></Box>}
      {query.isError && <Alert severity="error">{errorMessage}</Alert>}
      {!query.isLoading && !query.isError && records.length === 0 && (
        <Alert severity="info">The backend returned no {resource.label.toLowerCase()} records.</Alert>
      )}

      <Grid container spacing={2}>
        {records.map((record, index) => {
          const title = recordTitle(record, `${resource.label} ${index + 1}`);
          const status = recordStatus(record);
          const summaryEntries = Object.entries(record).filter(([, value]) => ["string", "number", "boolean"].includes(typeof value)).slice(0, 5);
          return (
            <Grid item xs={12} md={6} xl={4} key={`${title}-${index}`}>
              <Card variant="outlined" className="metric-card" sx={{ height: "100%" }}>
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" gap={1}>
                    <Typography variant="h6" sx={{ wordBreak: "break-word" }}>{title}</Typography>
                    {status && <Chip size="small" color={statusColour(status)} label={status} />}
                  </Stack>
                  <Stack spacing={0.7} mt={2} minHeight={102}>
                    {summaryEntries.map(([key, value]) => (
                      <Stack direction="row" justifyContent="space-between" gap={2} key={key}>
                        <Typography variant="caption" color="text.secondary">{key.replace(/_/g, " ")}</Typography>
                        <Typography variant="body2" fontWeight={650} textAlign="right" sx={{ wordBreak: "break-word" }}>{String(value)}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                  <Button sx={{ mt: 2 }} onClick={() => void openRecord(record)}>Inspect</Button>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      <Dialog open={Boolean(selected)} onClose={() => setSelected(null)} fullWidth maxWidth="md">
        <DialogTitle>{selected ? recordTitle(selected, "Resource details") : "Resource details"}</DialogTitle>
        <DialogContent dividers>
          {detailLoading ? <CircularProgress /> : detailError ? <Alert severity="error">{detailError}</Alert> : (
            <Box component="pre" sx={{ m: 0, p: 2, bgcolor: "grey.100", borderRadius: 2, overflow: "auto", fontSize: 12 }}>{pretty(detail)}</Box>
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setSelected(null)}>Close</Button></DialogActions>
      </Dialog>
    </Stack>
  );
}
