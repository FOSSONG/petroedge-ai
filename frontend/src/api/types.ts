import type {
  components,
  paths,
} from "./generated";

/**
 * Extracts an application/json payload from an OpenAPI request or
 * response object. Some generated operations expose the schema
 * directly, while others wrap it inside a content property.
 */
type JsonPayload<T> =
  T extends {
    content: {
      "application/json": infer Payload;
    };
  }
    ? Payload
    : T;

type RequiredValue<T> =
  Exclude<T, null | undefined>;

type WellsListOperation =
  RequiredValue<
    paths["/api/v1/wells"]["get"]
  >;

type WellDetailsOperation =
  RequiredValue<
    paths["/api/v1/wells/{well_id}"]["get"]
  >;

type WellLogsOperation =
  RequiredValue<
    paths["/api/v1/wells/{well_id}/logs"]["get"]
  >;

type WellAlertsOperation =
  RequiredValue<
    paths["/api/v1/wells/{well_id}/alerts"]["get"]
  >;

type SampleAnalysisOperation =
  RequiredValue<
    paths["/api/v1/analytics/sample"]["post"]
  >;

/**
 * OpenAPI-generated backend schema aliases.
 *
 * generated.ts remains the source of truth for endpoint contracts.
 */
export type ApiSchemas =
  components["schemas"];

export type WellSummary =
  components["schemas"]["WellSummary"];

export type WellLogSample =
  components["schemas"]["WellLogSample"];

export type AnalyticsResult =
  components["schemas"]["AnalyticsResult"];

export type WellsListResponse =
  JsonPayload<
    WellsListOperation["responses"][200]
  >;

export type WellDetailsResponse =
  JsonPayload<
    WellDetailsOperation["responses"][200]
  >;

export type WellLogsResponse =
  JsonPayload<
    WellLogsOperation["responses"][200]
  >;

export type WellAlertsResponse =
  JsonPayload<
    WellAlertsOperation["responses"][200]
  >;

export type SampleAnalysisRequest =
  JsonPayload<
    RequiredValue<
      SampleAnalysisOperation["requestBody"]
    >
  >;

export type SampleAnalysisResponse =
  JsonPayload<
    SampleAnalysisOperation["responses"][200]
  >;

/**
 * Authenticated frontend session model.
 */
export interface AuthenticatedUser {
  id?: string;
  uid?: string;
  email: string;
  name?: string;
  full_name?: string;
  roles?: string[];
  permissions?: string[];
  is_active?: boolean;
  [key: string]: unknown;
}

export interface LoginResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  user?: AuthenticatedUser;
  roles?: unknown;
  [key: string]: unknown;
}

/**
 * Operational alert model.
 */
export interface AlertRecord {
  id?: string;
  alert_id?: string;
  well_id?: string;
  title?: string;
  message?: string;
  description?: string;
  recommendation?: string;
  severity?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  [key: string]: unknown;
}

/**
 * Background processing job model.
 */
export interface BackgroundJob {
  id?: string;
  job_id?: string;
  name?: string;
  job_name?: string;
  job_type?: string;
  type?: string;
  status?: string;
  state?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  result?: unknown;
  error?: unknown;
  [key: string]: unknown;
}

export interface DashboardActivity {
  id?: string;
  type?: string;
  title?: string;
  message?: string;
  timestamp?: string;
  created_at?: string;
  [key: string]: unknown;
}

/**
 * Dashboard sections are flexible because the backend returns
 * dynamically grouped operational metrics.
 */
export interface DashboardSnapshot {
  generated_at?: string;

  overview?: Record<string, unknown>;
  operational?: Record<string, unknown>;
  data_quality?: Record<string, unknown>;
  model_performance?: Record<string, unknown>;
  reservoir_insights?: Record<string, unknown>;
  alert_metrics?: Record<string, unknown>;

  total_wells?: number;
  active_wells?: number;
  total_alerts?: number;
  active_alerts?: number;
  critical_alerts?: number;
  jobs_running?: number;
  completed_jobs?: number;
  models_registered?: number;
  data_quality_score?: number;
  model_accuracy?: number;

  recent_activity?: DashboardActivity[];
  activities?: DashboardActivity[];

  [key: string]: unknown;
}

export interface RegisteredModel {
  id?: string;
  model_id?: string;
  name?: string;
  model_name?: string;
  version?: string;
  status?: string;
  framework?: string;
  task?: string;
  accuracy?: number;
  metrics?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface ModelStatus {
  status?: string;
  health?: string;
  registered_models?: RegisteredModel[];
  models?: RegisteredModel[];
  active_model?: RegisteredModel;
  generated_at?: string;
  [key: string]: unknown;
}

export interface AuthenticationStatus {
  setup_required: boolean;
  user_count: number;
  manual_login: boolean;
}

export interface BootstrapAdministratorPayload {
  email: string;
  full_name: string;
  password: string;
  confirm_password: string;
}