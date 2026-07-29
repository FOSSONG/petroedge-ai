import { apiRequest } from "../../api/http";

export type ModelTask =
  | "hydrocarbon_classification"
  | "fluid_type_classification"
  | "reservoir_quality_classification"
  | "pay_zone_classification"
  | "lithology_classification"
  | "facies_classification"
  | "porosity_regression"
  | "permeability_regression"
  | "water_saturation_regression"
  | "anomaly_detection"
  | "sequence_interpretation";

export interface ModelManifest {
  model_id: string;
  display_name: string;
  task: ModelTask;
  algorithm: string;
  framework: string;
  version: string;
  stage: string;
  feature_schema: string[];
  metrics: Record<string, number>;
  resource_profile: string;
  enabled: boolean;
}

export async function listModels(task?: ModelTask): Promise<ModelManifest[]> {
  const query = task ? `?task=${encodeURIComponent(task)}` : "";
  return apiRequest<ModelManifest[]>(`/models${query}`);
}

export async function runModelInference(payload: {
  task: ModelTask;
  model_id?: string;
  records: Array<Record<string, unknown>>;
  explain?: boolean;
}) {
  return apiRequest("/models/infer", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}