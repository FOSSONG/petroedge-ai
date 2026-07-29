import { apiRequest } from "../../api/http";

export interface PlatformOverview {
  version: string;
  datasets: number;
  experiments: number;
  completed_experiments: number;
  registered_models: number;
  production_models: number;
  capabilities: string[];
}

export interface DatasetSummary {
  dataset_id: string;
  name: string;
  description?: string | null;
  source_type: string;
  file_name: string;
  file_size_bytes: number;
  row_count?: number | null;
  column_count?: number | null;
  columns: string[];
  missing_values: Record<string, number>;
  status: string;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentSummary {
  experiment_id: string;
  name: string;
  task: string;
  dataset_id?: string | null;
  algorithm: string;
  model_id?: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  parameters: Record<string, unknown>;
  metrics: Record<string, unknown>;
  training_seconds?: number | null;
  model_size_bytes?: number | null;
  validation_strategy?: string | null;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
  progress_percent: number;
  current_stage?: string | null;
  error_message?: string | null;
}

export interface DatasetPreview {
  dataset_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
}

export interface ReportResult {
  report_id: string;
  generated_files: Record<string, string>;
  title: string;
}

export interface ExperimentCreate {
  name: string;
  task: string;
  dataset_id?: string | null;
  algorithm: string;
  model_id?: string | null;
  status?: ExperimentSummary["status"];
  parameters?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  validation_strategy?: string | null;
}

export const fetchPlatformOverview = () => apiRequest<PlatformOverview>("/platform/overview");
export const fetchDatasets = () => apiRequest<DatasetSummary[]>("/platform/datasets");
export const fetchExperiments = () => apiRequest<ExperimentSummary[]>("/platform/experiments");
export const deleteDataset = (datasetId: string) => apiRequest<void>(`/platform/datasets/${datasetId}`, { method: "DELETE" });

export function uploadDataset(name: string, description: string, file: File) {
  const body = new FormData();
  body.append("name", name);
  if (description.trim()) body.append("description", description.trim());
  body.append("file", file);
  return apiRequest<DatasetSummary>("/platform/datasets", { method: "POST", body });
}

export function createExperiment(payload: ExperimentCreate) {
  return apiRequest<ExperimentSummary>("/platform/experiments", {
    method: "POST",
    body: JSON.stringify({
      status: "queued",
      parameters: {},
      metrics: {},
      ...payload,
    }),
  });
}

export const fetchDatasetPreview = (datasetId: string) => apiRequest<DatasetPreview>(`/platform/datasets/${datasetId}/preview?limit=800`);

export function generateDatasetReport(datasetId: string) {
  return apiRequest<ReportResult>(`/reports/dataset/${datasetId}`, {
    method: "POST",
    body: JSON.stringify({ formats: ["pdf", "html", "json"], include_recommendations: true }),
  });
}

export async function downloadReport(reportId: string, format = "pdf") {
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000/api/v1";
  const token = localStorage.getItem("petroedge_access_token") ?? sessionStorage.getItem("petroedge_access_token");
  const response = await fetch(`${base}/reports/${reportId}/download?format=${format}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new Error(`Report download failed (${response.status}).`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `petroedge-report-${reportId}.${format}`; anchor.click(); URL.revokeObjectURL(url);
}

export interface InterpretationResult {
  dataset: DatasetSummary;
  curve_mapping: Record<string, string | null>;
  summary: Record<string, unknown>;
  intervals: Array<Record<string, unknown>>;
  samples: Array<Record<string, unknown>>;
}
export interface LasWizardResult { dataset_id:string; detected_curves:string[]; mnemonic_mapping:Record<string,string|null>; qc:{row_count:number;missing_cells:number;duplicate_rows:number;ready:boolean}; missing_recommended_curves:string[]; steps:string[]; }
export interface ReplayResult { dataset_id:string; event_count:number; events:Array<{sequence:number;depth:number;logs:Record<string,number>;prediction:Record<string,string|number>;alerts:string[]}>; }
export const fetchInterpretation=(datasetId:string)=>apiRequest<InterpretationResult>(`/v1/datasets/${datasetId}/interpretation`);
export const fetchLasWizard=(datasetId:string)=>apiRequest<LasWizardResult>(`/v1/datasets/${datasetId}/las-wizard`);
export const fetchReplay=(datasetId:string,topDepth?:number,bottomDepth?:number)=>{
 const params=new URLSearchParams({limit:"1000"});
 if(Number.isFinite(topDepth))params.set("top_depth",String(topDepth));
 if(Number.isFinite(bottomDepth))params.set("bottom_depth",String(bottomDepth));
 return apiRequest<ReplayResult>(`/v1/datasets/${datasetId}/replay?${params.toString()}`);
};
export interface AssistantResponse { question:string; intent:string; answer:string; evidence:string[]; grounded:boolean; explanation:{depth:number;prediction:string;lithology:string;confidence:number;porosity:number;water_saturation:number;feature_importance:Array<{feature:string;contribution:number}>}; intervals:Array<{top_depth:number;base_depth:number;samples:number}>; }
export const askAssistant=(datasetId:string,question:string)=>apiRequest<AssistantResponse>(`/v1/datasets/${datasetId}/assistant`,{method:"POST",body:JSON.stringify({question})});
export interface EdgeRuntimeStatus {device_id:string;device_name:string;status:string;runtime:string;cpu_percent:number;memory_percent:number;queue_depth:number;inference_latency_ms:number;sync_status:string;last_heartbeat:string;deployment_target:string;}
export const fetchEdgeRuntime=()=>apiRequest<EdgeRuntimeStatus>(`/v1/edge-runtime`);
export const fetchAssets=()=>apiRequest<Array<{asset_id:string;field:string;well:string;dataset_id?:string|null;status:string}>>(`/v1/assets`);
export const saveAsset=(payload:{field:string;well:string;dataset_id?:string|null})=>apiRequest(`/v1/assets`,{method:"POST",body:JSON.stringify(payload)});
export const fetchModules=()=>apiRequest<Array<{module:string;slug:string;status:string;mvp_functional:boolean}>>(`/v1/modules`);
export async function downloadV1Report(datasetId:string){
 const base=(import.meta.env.VITE_API_BASE_URL as string|undefined)??"http://127.0.0.1:8000/api/v1";
 const token=localStorage.getItem("petroedge_access_token")??sessionStorage.getItem("petroedge_access_token");
 const response=await fetch(`${base}/v1/datasets/${datasetId}/report.pdf`,{headers:token?{Authorization:`Bearer ${token}`}:{}});
 if(!response.ok)throw new Error(`Report generation failed (${response.status}).`);
 const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`petroedge-${datasetId}.pdf`;a.click();URL.revokeObjectURL(url);
}

export interface OperationsResponse {
  generated_at:string;
  summary:Record<string,number>;
  current_dataset:(Partial<DatasetSummary>&{name?:string;file_name?:string;status?:string})|null;
  processing_queue:Array<{id?:string;name?:string;task?:string;status?:string;progress?:number;stage?:string|null;dataset_id?:string|null}>;
  services:Array<{name?:string;status?:string;detail?:string}>;
  workflow:Array<{name?:string;status?:string;message?:string;order?:number}>;
}
export interface CalibrationResponse {
  region:string;calibration_name:string;status:string;formations:string[];datasets:number;validated_datasets:number;training_samples:number;supported_curves:string[];governance:string;last_updated:string;
}
export interface ContinualLearningResponse {
  knowledge_base:{eligible_datasets:number;admitted_datasets:number};
  retraining_queue:Array<{dataset_id:string;name:string;status:string}>;
  model_candidates:Array<Record<string,unknown>>;
  controls:string[];
}
export const fetchSprint2Operations=()=>apiRequest<OperationsResponse>("/sprint2/operations");
export const fetchCalibration=()=>apiRequest<CalibrationResponse>("/sprint2/calibration");
export const fetchContinualLearning=()=>apiRequest<ContinualLearningResponse>("/sprint2/learning");
