import { apiRequest } from "../../api/http";

export interface WorkflowNode {
  id: string;
  type: string;
  name?: string | null;
  parameters: Record<string, unknown>;
  depends_on: string[];
  enabled: boolean;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  version: string;
  tags: string[];
  nodes: WorkflowNode[];
  metadata: Record<string, unknown>;
}

export interface WorkflowListResponse {
  count: number;
  workflows: WorkflowDefinition[];
}

export interface WorkflowNodeRunResult {
  node_id: string;
  node_type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  started_at: string;
  finished_at?: string | null;
  output: Record<string, unknown>;
  error?: string | null;
}

export interface WorkflowRun {
  run_id: string;
  workflow_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  node_results: WorkflowNodeRunResult[];
  error?: string | null;
}

export const fetchWorkflows = () =>
  apiRequest<WorkflowListResponse>("/workflows");

export const runWorkflow = (
  workflowId: string,
  rows: Record<string, unknown>[],
  datasetId: string,
) =>
  apiRequest<WorkflowRun>(`/workflows/${workflowId}/run`, {
    method: "POST",
    body: JSON.stringify({
      inputs: {
        rows,
        dataset_id: datasetId,
      },
      parameters: {
        source: "dataset_registry",
      },
    }),
  });
