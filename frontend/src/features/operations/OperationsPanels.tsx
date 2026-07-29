import { Alert, Card, CardContent, Chip, Grid, Stack, Typography } from "@mui/material";
import { AgentsWorkspace } from "./AgentsWorkspace";
import { WorkflowsWorkspace } from "./WorkflowsWorkspace";
import { PluginsWorkspace } from "./PluginsWorkspace";
import { EdgeWorkspace } from "./EdgeWorkspace";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ResourcePanel } from "./ResourcePanel";
import { JsonActionDialog } from "./JsonActionDialog";
import { fetchResource, resources, type JsonRecord } from "./operationsApi";

function stringId(record: JsonRecord, keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return encodeURIComponent(value);
    if (typeof value === "number") return encodeURIComponent(String(value));
  }
  return null;
}

export function AgentsPanel() { return <AgentsWorkspace />; }

export function WorkflowsPanel() { return <WorkflowsWorkspace />; }

export function TwinsPanel() {
  return <ResourcePanel resource={resources.twins} detailPath={(record) => {
    const id = stringId(record, ["reservoir_id", "twin_id", "id"]);
    return id ? `/twins/${id}` : null;
  }} actions={<JsonActionDialog label="Create twin" title="Create a digital twin" path="/twins" initialPayload={{ reservoir_id: "PETROEDGE-DEMO-RESERVOIR", name: "Demo reservoir twin", metadata: {} }} />} />;
}

export function RulesPanel() {
  return <ResourcePanel resource={resources.rules} detailPath={(record) => {
    const id = stringId(record, ["rule_id", "id"]);
    return id ? `/rules/${id}` : null;
  }} actions={<JsonActionDialog label="Create rule" title="Create an operational rule" path="/rules" initialPayload={{ name: "High water saturation", enabled: true, condition: { field: "water_saturation", operator: ">", value: 0.65 }, action: { severity: "warning" } }} />} />;
}

export function EventsPanel() {
  return <ResourcePanel resource={resources.events} />;
}

export function PluginsPanel() { return <PluginsWorkspace />; }

export function EdgePanel() { return <EdgeWorkspace />; }

export function ReportsPanel() {
  return <ResourcePanel resource={resources.reports} detailPath={(record) => {
    const id = stringId(record, ["report_id", "id"]);
    return id ? `/reports/${id}` : null;
  }} actions={<JsonActionDialog label="Generate report" title="Generate a report" path="/reports/generate" initialPayload={{ report_type: "operational", title: "PetroEdge operational report", formats: ["pdf", "html"] }} />} />;
}

interface HealthCardProps { title: string; path: string; }
function HealthValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <Stack direction="row" gap={0.75} flexWrap="wrap">{value.map((item, index) => <Chip size="small" key={`${String(item)}-${index}`} label={typeof item === "object" ? `Item ${index + 1}` : String(item)} />)}</Stack>;
  if (typeof value === "boolean") return <Chip size="small" color={value ? "success" : "error"} label={value ? "Operational" : "Unavailable"} />;
  if (value && typeof value === "object") return <Stack spacing={0.75}>{Object.entries(value as JsonRecord).map(([key, nested]) => <Stack key={key} direction="row" justifyContent="space-between" gap={2}><Typography variant="body2" color="text.secondary">{key.replace(/_/g, " ")}</Typography><HealthValue value={nested}/></Stack>)}</Stack>;
  const label = String(value ?? "Not reported");
  const healthy = /healthy|ok|running|operational|available|ready/i.test(label);
  return <Chip size="small" color={healthy ? "success" : "default"} label={label} />;
}

function HealthCard({ title, path }: HealthCardProps) {
  const query = useQuery({ queryKey: ["health", path], queryFn: () => fetchResource(path), refetchInterval: 30000, retry: 1 });
  const data = query.data && typeof query.data === "object" ? query.data as JsonRecord : { status: query.data };
  return <Card variant="outlined" className="metric-card"><CardContent><Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="h6">{title}</Typography><Chip size="small" variant="outlined" label="30 s refresh"/></Stack>{query.isError ? <Alert severity="error" sx={{ mt: 2 }}>{query.error instanceof Error ? query.error.message : "Unavailable"}</Alert> : query.isLoading ? <Typography color="text.secondary" mt={2}>Checking service…</Typography> : <Stack spacing={1.25} mt={2}>{Object.entries(data).map(([key, value]) => <Stack key={key} direction="row" justifyContent="space-between" alignItems="flex-start" gap={2} sx={{ p: 1.25, bgcolor: "grey.50", borderRadius: 1.5 }}><Typography variant="body2" fontWeight={700} sx={{ textTransform: "capitalize" }}>{key.replace(/_/g, " ")}</Typography><HealthValue value={value}/></Stack>)}</Stack>}</CardContent></Card>;
}

export function MonitoringPanel() {
  return <Stack spacing={2.5}><Card className="feature-hero" variant="outlined"><CardContent sx={{ p: 3, position: "relative", zIndex: 1 }}><Typography variant="h4">System monitoring</Typography><Typography sx={{ mt: 1 }}>Live health checks for the API, background jobs, real-time gateway, models and monitoring services.</Typography></CardContent></Card><Grid container spacing={2}>{[
    ["Dashboard health", "/dashboard/health"],
    ["Monitoring", "/monitoring/health"],
    ["Background jobs", "/jobs/health"],
    ["Real-time gateway", "/realtime/health"],
  ].map(([title, path]) => <Grid item xs={12} md={6} key={path}><HealthCard title={title} path={path} /></Grid>)}</Grid></Stack>;
}
