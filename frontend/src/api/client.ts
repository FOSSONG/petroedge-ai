import {
  apiRequest,
  clearAccessToken,
  setAccessToken,
} from "./http";

import type {
  AlertRecord,
  AnalyticsResult,
  BackgroundJob,
  DashboardSnapshot,
  LoginResponse,
  ModelStatus,
  WellLogSample,
} from "./types";

interface LoginPayload {
  username: string;
  password: string;
  mfa_code?: string;
}

export function setToken(token: string): void {
  setAccessToken(token);
}

export function logout(): void {
  clearAccessToken();
}

export async function login(
  username: string,
  password: string,
  mfaCode?: string,
): Promise<LoginResponse> {
  const payload: LoginPayload = {
    username: username.trim().toLowerCase(),
    password,
  };

  const cleanedMfaCode = mfaCode?.trim();

  if (cleanedMfaCode) {
    payload.mfa_code = cleanedMfaCode;
  }

  const response = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.access_token) {
    throw new Error(
      "Authentication succeeded, but no access token was returned.",
    );
  }

  setAccessToken(response.access_token);

  return response;
}

export function fetchCurrentUser() {
  return apiRequest("/auth/me");
}

export function fetchDashboard(): Promise<DashboardSnapshot> {
  return apiRequest<DashboardSnapshot>("/dashboard");
}

export function fetchLogs(
  wellId = "PETROEDGE-DEMO-01",
): Promise<WellLogSample[]> {
  return apiRequest<WellLogSample[]>(
    `/wells/${encodeURIComponent(wellId)}/logs`,
  );
}

export function fetchAlerts(): Promise<AlertRecord[]> {
  return apiRequest<AlertRecord[]>("/alerts");
}

export function fetchModelStatus(): Promise<ModelStatus> {
  return apiRequest<ModelStatus>("/models");
}

export function analyzeSample(
  sample: WellLogSample,
): Promise<AnalyticsResult> {
  return apiRequest<AnalyticsResult>("/analytics/sample", {
    method: "POST",
    body: JSON.stringify(sample),
  });
}

export function createJob(
  taskName: string,
  payload: Record<string, unknown>,
  priority = 100,
  maxAttempts = 3,
): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>("/jobs", {
    method: "POST",
    body: JSON.stringify({
      task_name: taskName,
      payload,
      priority,
      max_attempts: maxAttempts,
    }),
  });
}

export function fetchJob(
  jobId: string,
): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>(
    `/jobs/${encodeURIComponent(jobId)}`,
  );
}

export function cancelJob(
  jobId: string,
): Promise<BackgroundJob> {
  return apiRequest<BackgroundJob>(
    `/jobs/${encodeURIComponent(jobId)}/cancel`,
    {
      method: "POST",
    },
  );
}