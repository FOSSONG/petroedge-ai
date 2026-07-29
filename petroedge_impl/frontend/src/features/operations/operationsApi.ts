import { apiRequest } from "../../api/http";

export type JsonRecord = Record<string, unknown>;

export interface ResourceDescriptor {
  key: string;
  label: string;
  path: string;
  description: string;
}

export const resources = {
  agents: { key: "agents", label: "Agents", path: "/agents", description: "Registered domain agents and orchestration capabilities." },
  workflows: { key: "workflows", label: "Workflows", path: "/workflows", description: "Workflow definitions and execution entry points." },
  twins: { key: "twins", label: "Digital twins", path: "/twins", description: "Reservoir digital-twin states and simulation resources." },
  rules: { key: "rules", label: "Rules", path: "/rules", description: "Operational decision and alerting rules." },
  events: { key: "events", label: "Events", path: "/events", description: "Platform events, audit records and stream history." },
  plugins: { key: "plugins", label: "Plugins", path: "/plugins/modules", description: "Installed extension modules and capabilities." },
  edge: { key: "edge", label: "Edge", path: "/edge/capabilities", description: "Edge deployments and runtime status." },
  reports: { key: "reports", label: "Reports", path: "/reports", description: "Generated analytical and operational reports." },
  monitoring: { key: "monitoring", label: "Monitoring", path: "/monitoring/health", description: "Backend service and model health." },
} satisfies Record<string, ResourceDescriptor>;

export function fetchResource<T = unknown>(path: string): Promise<T> {
  return apiRequest<T>(path);
}

export function postResource<T = unknown>(path: string, payload: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function putResource<T = unknown>(path: string, payload: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteResource<T = unknown>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "DELETE" });
}

export function asRecords(value: unknown): JsonRecord[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is JsonRecord => typeof item === "object" && item !== null);
  }

  if (typeof value !== "object" || value === null) {
    return [];
  }

  const record = value as JsonRecord;
  for (const key of ["items", "results", "data", "agents", "workflows", "twins", "rules", "events", "plugins", "reports", "models", "deployments"]) {
    const candidate = record[key];
    if (Array.isArray(candidate)) {
      return candidate.filter((item): item is JsonRecord => typeof item === "object" && item !== null);
    }
  }

  return [record];
}

export function recordTitle(record: JsonRecord, fallback: string): string {
  for (const key of ["name", "title", "label", "agent_name", "workflow_name", "reservoir_id", "twin_id", "rule_id", "event_type", "plugin_name", "report_id", "id"]) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return fallback;
}

export function recordStatus(record: JsonRecord): string | undefined {
  for (const key of ["status", "state", "health", "enabled", "active"]) {
    const value = record[key];
    if (typeof value === "string") return value;
    if (typeof value === "boolean") return value ? "active" : "inactive";
  }
  return undefined;
}
