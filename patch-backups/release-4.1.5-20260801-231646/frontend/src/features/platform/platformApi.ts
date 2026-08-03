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
  version_id: string;
  version_number: number;
  parent_dataset_id?: string | null;
  root_dataset_id: string;
  dataset_type: string;
  name: string;
  description?: string | null;
  source_type: string;
  file_name: string;
  file_size_bytes: number;
  checksum_sha256: string;
  row_count?: number | null;
  column_count?: number | null;
  columns: string[];
  missing_values: Record<string, number>;
  units: Record<string, string>;
  metadata: Record<string, unknown>;
  processing: Record<string, unknown>;
  field_name?: string | null;
  well_name?: string | null;
  reservoir_name?: string | null;
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
export const fetchDatasets = async () => {
  const response = await apiRequest<unknown>("/platform/datasets");
  if (Array.isArray(response)) return response as DatasetSummary[];
  if (response && typeof response === "object") {
    const record = response as Record<string, unknown>;
    for (const key of ["datasets", "items", "results", "data"]) if (Array.isArray(record[key])) return record[key] as DatasetSummary[];
  }
  return [];
};
export const fetchExperiments = async () => {
  const response = await apiRequest<unknown>("/platform/experiments");
  const values = Array.isArray(response) ? response : response && typeof response === "object"
    ? (["experiments", "items", "results", "data"].map((key) => (response as Record<string, unknown>)[key]).find(Array.isArray) ?? [])
    : [];
  return (values as Array<Record<string, unknown>>).map((item) => ({
    ...item,
    metrics: item.metrics && typeof item.metrics === "object" && !Array.isArray(item.metrics) ? item.metrics : {},
    parameters: item.parameters && typeof item.parameters === "object" && !Array.isArray(item.parameters) ? item.parameters : {},
    progress_percent: Number.isFinite(Number(item.progress_percent)) ? Number(item.progress_percent) : 0,
  })) as ExperimentSummary[];
};
export const deleteDataset = (datasetId: string) => apiRequest<void>(`/platform/datasets/${datasetId}`, { method: "DELETE" });

export function uploadDataset(name: string, description: string, file: File, datasetType="well_log", fieldName="", wellName="", reservoirName="") {
  const body = new FormData();
  body.append("name", name);
  if (description.trim()) body.append("description", description.trim());
  body.append("dataset_type", datasetType);
  if(fieldName.trim()) body.append("field_name",fieldName.trim());
  if(wellName.trim()) body.append("well_name",wellName.trim());
  if(reservoirName.trim()) body.append("reservoir_name",reservoirName.trim());
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

export const fetchDatasetPreview = (datasetId: string, limit = 120) => apiRequest<DatasetPreview>(`/platform/datasets/${datasetId}/preview?limit=${Math.max(1, Math.min(limit, 500))}`);

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
  summary: Record<string, number | string>;
  intervals: Array<Record<string, unknown>>;
  samples: Array<Record<string, number | string>>;
}
export interface LasWizardResult { dataset_id:string; detected_curves:string[]; mnemonic_mapping:Record<string,string|null>; qc:{row_count:number;missing_cells:number;duplicate_rows:number;ready:boolean}; missing_recommended_curves:string[]; steps:string[]; }
export interface ReplayResult { dataset_id:string; event_count:number; events:Array<{sequence:number;depth:number;logs:Record<string,number>;prediction:Record<string,string|number>;alerts:string[]}>; }
export const fetchInterpretation=(datasetId:string)=>apiRequest<InterpretationResult>(`/datasets/${datasetId}/interpretation`);
export const fetchLasWizard=(datasetId:string)=>apiRequest<LasWizardResult>(`/datasets/${datasetId}/las-wizard`);
export const fetchReplay=(datasetId:string,topDepth?:number,bottomDepth?:number)=>{
 const params=new URLSearchParams({limit:"1000"});
 if(Number.isFinite(topDepth))params.set("top_depth",String(topDepth));
 if(Number.isFinite(bottomDepth))params.set("bottom_depth",String(bottomDepth));
 return apiRequest<ReplayResult>(`/datasets/${datasetId}/replay?${params.toString()}`);
};
export interface AssistantResponse { question:string; intent:string; answer:string; evidence:string[]; grounded:boolean; explanation:{depth:number;prediction:string;lithology:string;confidence:number;porosity:number;water_saturation:number;feature_importance:Array<{feature:string;contribution:number}>}; intervals:Array<{top_depth:number;base_depth:number;samples:number}>; }
export const askAssistant=(datasetId:string,question:string)=>apiRequest<AssistantResponse>(`/datasets/${datasetId}/assistant`,{method:"POST",body:JSON.stringify({question})});
export interface EdgeRuntimeStatus {device_id:string;device_name:string;status:string;runtime:string;cpu_percent:number;memory_percent:number;queue_depth:number;inference_latency_ms:number;sync_status:string;last_heartbeat:string;deployment_target:string;}
export const fetchEdgeRuntime=()=>apiRequest<EdgeRuntimeStatus>(`/edge-runtime`);
export const fetchAssets=()=>apiRequest<Array<{asset_id:string;field:string;well:string;dataset_id?:string|null;status:string}>>(`/assets`);
export const saveAsset=(payload:{field:string;well:string;dataset_id?:string|null})=>apiRequest(`/assets`,{method:"POST",body:JSON.stringify(payload)});
export const fetchModules=()=>apiRequest<Array<{module:string;slug:string;status:string;mvp_functional:boolean}>>(`/modules`);
export async function downloadV1Report(datasetId: string) {
  const base =
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    "http://127.0.0.1:8000/api/v1";

  const token =
    localStorage.getItem("petroedge_access_token") ??
    sessionStorage.getItem("petroedge_access_token");

  const response = await fetch(
    `${base}/datasets/${datasetId}/report.pdf`,
    {
      headers: token
        ? { Authorization: `Bearer ${token}` }
        : {},
    },
  );

  if (!response.ok) {
    let detail = "";

    try {
      const payload = await response.json() as {
        detail?: string;
      };

      detail = payload.detail
        ? ` ${payload.detail}`
        : "";
    } catch {
      detail = "";
    }

    throw new Error(
      `Report generation failed (${response.status}).${detail}`,
    );
  }

  const contentType =
    response.headers.get("content-type") ?? "";

  if (!contentType.toLowerCase().includes("application/pdf")) {
    throw new Error(
      `The report endpoint returned ${contentType || "an unknown content type"} instead of a PDF.`,
    );
  }

  const blob = await response.blob();

  if (blob.size === 0) {
    throw new Error("The generated PDF file is empty.");
  }

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = url;
  anchor.download = `petroedge-${datasetId}.pdf`;
  anchor.style.display = "none";

  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 3000);
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

export interface DatasetLineage { dataset:DatasetSummary; parents:string[]; children:string[]; operations:Array<Record<string,unknown>>; }
export const fetchDatasetLineage=(datasetId:string)=>apiRequest<DatasetLineage>(`/platform/datasets/${datasetId}/lineage`);
export const processLasDataset=(datasetId:string,payload:Record<string,unknown>={})=>apiRequest<DatasetSummary>(`/platform/datasets/${datasetId}/process-las`,{method:"POST",body:JSON.stringify(payload)});

export interface CcusScreenPayload {
  dataset_id?: string | null; project_name:string; storage_type:"saline_aquifer"|"depleted_reservoir";
  area_km2:number; net_thickness_m:number; porosity_fraction:number; co2_density_kg_m3:number;
  storage_efficiency_fraction:number; permeability_md:number; depth_m:number;
  initial_pressure_mpa:number; fracture_pressure_mpa:number; caprock_thickness_m?:number|null;
  fault_risk:"low"|"medium"|"high"|"unknown"; pressure_data_available:boolean;
  seal_data_available:boolean; fault_data_available:boolean; geomechanics_available:boolean;
}
export interface CcusRunSummary {
  run_id:string; project_name:string; dataset_id?:string|null; dataset_name?:string|null;
  field_name?:string|null; well_name?:string|null; reservoir_name?:string|null; storage_type:string;
  capacity_mt:number; pore_volume_m3:number; suitability_score:number; suitability_class:string;
  injectivity_score:number; containment_score:number; data_quality_score:number; pressure_margin_mpa:number;
  risk_flags:string[]; recommendations:string[]; inputs:Record<string,unknown>;
  methodology:Record<string,unknown>; created_at:string;
}
export const fetchCcusCapabilities=()=>apiRequest<{status:string;version:string;capabilities:string[];limitations:string[]}>("/ccus/capabilities");
export const fetchCcusRuns=()=>apiRequest<CcusRunSummary[]>("/ccus/runs");
export const createCcusScreen=(payload:CcusScreenPayload)=>apiRequest<CcusRunSummary>("/ccus/screen",{method:"POST",body:JSON.stringify(payload)});
export const deleteCcusRun=(runId:string)=>apiRequest<void>(`/ccus/runs/${runId}`,{method:"DELETE"});
export interface ReservoirTwin {
  reservoir_id:string;
  name:string;
  version?:number;
  status?:string;
  wells?:Record<string,Record<string,unknown>>;
  reservoir?:Record<string,unknown>;
  metrics?:Record<string,unknown>;
  metadata?:Record<string,unknown>;
  updated_at?:string;
  created_at?:string;
  [key:string]:unknown;
}
export interface TwinListResponse {count:number;twins:ReservoirTwin[]}
export interface TwinHistoryResponse {reservoir_id:string;count:number;snapshots:Array<Record<string,unknown>>}
export interface TwinWorkspaceSummary {
 twin:ReservoirTwin;health:Record<string,unknown>;history_count:number;latest_version?:number|null;
 methodology:{classification:string;scenario_mode:string;limitations:string[]};
}
export interface TwinScenarioResponse {
 reservoir_id:string;scenario_name:string;persisted:boolean;baseline:Record<string,unknown>;
 scenario:Record<string,unknown>;changes:Array<{path:string;operation:string;before:unknown;after:unknown}>;warning:string;
}
export const fetchTwins=()=>apiRequest<TwinListResponse>("/twins");
export const createTwin=(payload:{reservoir_id:string;name:string})=>apiRequest<ReservoirTwin>("/twins",{method:"POST",body:JSON.stringify(payload)});
export const fetchTwin=(reservoirId:string)=>apiRequest<ReservoirTwin>(`/twins/${reservoirId}`);
export const fetchTwinHealth=(reservoirId:string)=>apiRequest<Record<string,unknown>>(`/twins/${reservoirId}/health`);
export const fetchTwinHistory=(reservoirId:string)=>apiRequest<TwinHistoryResponse>(`/twins/${reservoirId}/history`);
export const restoreTwinVersion=(reservoirId:string,version:number)=>apiRequest<ReservoirTwin>(`/twins/${reservoirId}/restore/${version}`,{method:"POST"});
export const deleteTwin=(reservoirId:string)=>apiRequest<void>(`/twins/${reservoirId}`,{method:"DELETE"});
export const fetchTwinWorkspaceSummary=(reservoirId:string)=>apiRequest<TwinWorkspaceSummary>(`/twin-workspace/${reservoirId}/summary`);
export const runTwinWorkspaceScenario=(reservoirId:string,payload:{name:string;adjustments:Array<{path:string;operation:"set"|"increase"|"decrease"|"multiply";value:number}>})=>
 apiRequest<TwinScenarioResponse>(`/twin-workspace/${reservoirId}/scenario`,{method:"POST",body:JSON.stringify(payload)});

export interface LifecycleAlgorithm {
  algorithm: "random_forest" | "xgboost" | "ann";
  display_name: string;
  available: boolean;
  engine: string;
  engine_version?: string | null;
  cpu_ready: boolean;
  supports: string[];
  unavailable_reason?: string | null;
}

export interface LifecycleModel {
  model_id: string;
  display_name: string;
  version: number;
  stage: string;
  algorithm: string;
  task_type: "regression" | "classification";
  dataset_id: string;
  target_column: string;
  feature_columns: string[];
  validation_strategy: string;
  metrics: Record<string, number | boolean>;
  artefact_size_bytes: number;
  configuration_hash: string;
  created_at: string;
}

export interface LifecycleTrainingPayload {
  display_name: string;
  dataset_id: string;
  algorithm: "random_forest" | "xgboost" | "ann";
  task_type: "regression" | "classification";
  target_column: string;
  feature_columns: string[];
  validation_strategy: "random" | "grouped" | "temporal";
  group_column?: string | null;
  time_column?: string | null;
  test_size: number;
  random_seed: number;
  hyperparameters: Record<string, unknown>;
}

export interface LifecycleTrainingResult {
  model_id: string;
  version: number;
  stage: string;
  metrics: Record<string, number | boolean>;
  artefact_path: string;
  manifest_path: string;
  configuration_hash: string;
  rows_used: number;
  training_rows: number;
  validation_rows: number;
}

export interface LifecyclePredictionResult {
  model_id: string;
  dataset_id: string;
  output_column: string;
  row_count: number;
  output_path: string;
  preview: Array<Record<string, unknown>>;
}

export const fetchLifecycleAlgorithms = () =>
  apiRequest<{ algorithms: LifecycleAlgorithm[] }>("/training-lifecycle/algorithms");

export const fetchLifecycleModels = () =>
  apiRequest<{ models: LifecycleModel[] }>("/training-lifecycle/registry");

export const trainLifecycleModel = (payload: LifecycleTrainingPayload) =>
  apiRequest<LifecycleTrainingResult>("/training-lifecycle/train", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export interface LifecycleDeleteResult {
  model_id: string;
  display_name: string;
  version: number | null;
  deleted: boolean;
}

export const deleteLifecycleModel = (modelId: string) =>
  apiRequest<LifecycleDeleteResult>(`/training-lifecycle/registry/${modelId}`, {
    method: "DELETE",
  });

export const updateLifecycleStage = (modelId: string, stage: string) =>
  apiRequest<LifecycleModel>(`/training-lifecycle/registry/${modelId}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage }),
  });

export const predictWithLifecycleModel = (payload: {
  dataset_id: string;
  model_id: string;
  output_column?: string | null;
}) =>
  apiRequest<LifecyclePredictionResult>("/training-lifecycle/predict", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const retrainLifecycleModel = (
  modelId: string,
  payload: {
    dataset_id?: string | null;
    display_name?: string | null;
    hyperparameters?: Record<string, unknown> | null;
  },
) =>
  apiRequest<LifecycleTrainingResult>(
    `/training-lifecycle/registry/${modelId}/retrain`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export interface DatasetQualityReport {
  dataset_id:string;
  blocking_errors:string[];
  warnings:string[];
  unit_warnings:string[];
  summary:Record<string,number>;
  column_quality:Array<{column:string;dtype:string;missing:number;missing_percent:number;null_codes:number;unique:number;unit:string;canonical_curve?:string|null}>;
  ready_for_training:boolean;
}
export interface DatasetPreparationPayload {
  name?:string|null; null_values:number[]; zero_as_null_columns:string[]; depth_column?:string|null;
  interpolate_limit:number; despike:boolean; smooth:boolean; clip_physical_ranges:boolean;
  scaling:"none"|"standard"|"minmax"|"robust"; scaling_columns:string[];
}
export const fetchDatasetQuality=(datasetId:string)=>apiRequest<DatasetQualityReport>(`/platform/datasets/${datasetId}/quality`);
export const prepareDataset=(datasetId:string,payload:DatasetPreparationPayload)=>apiRequest<DatasetSummary>(`/platform/datasets/${datasetId}/prepare`,{method:"POST",body:JSON.stringify(payload)});
export const editDataset=(datasetId:string,payload:{name?:string|null;operations:Array<Record<string,unknown>>})=>apiRequest<DatasetSummary>(`/platform/datasets/${datasetId}/edit`,{method:"POST",body:JSON.stringify(payload)});

async function downloadAuthenticated(path:string,filename:string){
 const base=(import.meta.env.VITE_API_BASE_URL as string|undefined)??"http://127.0.0.1:8000/api/v1";
 const token=localStorage.getItem("petroedge_access_token")??sessionStorage.getItem("petroedge_access_token");
 const response=await fetch(`${base}${path}`,{headers:token?{Authorization:`Bearer ${token}`}:{}});
 if(!response.ok)throw new Error(`Download failed (${response.status}).`);
 const blob=await response.blob(); const url=URL.createObjectURL(blob); const a=document.createElement("a");
 a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
export const downloadDatasetFile=(datasetId:string,filename:string)=>downloadAuthenticated(`/platform/datasets/${datasetId}/download`,filename);
export const downloadPredictionFile=(outputPath:string)=>{const name=outputPath.split(/[\\/]/).pop()||"predictions.csv";return downloadAuthenticated(`/training-lifecycle/predictions/${encodeURIComponent(name)}/download`,name)};
