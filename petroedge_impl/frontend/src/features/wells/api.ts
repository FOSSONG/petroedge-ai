import { apiRequest } from "../../api/http";

import type {
  SampleAnalysisRequest,
  SampleAnalysisResponse,
  WellAlertsResponse,
  WellDetailsResponse,
  WellLogsResponse,
  WellsListResponse,
} from "../../api/types";

export async function fetchWells(): Promise<WellsListResponse> {
  return apiRequest<WellsListResponse>("/wells");
}

export async function fetchWell(
  wellId: string,
): Promise<WellDetailsResponse> {
  return apiRequest<WellDetailsResponse>(
    `/wells/${encodeURIComponent(wellId)}`,
  );
}

export async function fetchWellLogs(
  wellId: string,
): Promise<WellLogsResponse> {
  return apiRequest<WellLogsResponse>(
    `/wells/${encodeURIComponent(wellId)}/logs`,
  );
}

export async function fetchWellAlerts(
  wellId: string,
): Promise<WellAlertsResponse> {
  return apiRequest<WellAlertsResponse>(
    `/wells/${encodeURIComponent(wellId)}/alerts`,
  );
}

export async function analyseSample(
  payload: SampleAnalysisRequest,
): Promise<SampleAnalysisResponse> {
  return apiRequest<SampleAnalysisResponse>(
    "/analytics/sample",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
