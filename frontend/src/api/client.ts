import axios from 'axios';
import type { Alert, AnalyticsResult, WellLogSample } from '../types';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const api = axios.create({ baseURL });

export function setToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export async function login(username: string, password: string, mfaCode: string) {
  const response = await api.post('/api/v1/auth/login', {
    username,
    password,
    mfa_code: mfaCode
  });
  return response.data as { access_token: string; roles: string[] };
}

export async function fetchLogs(wellId = 'PETROEDGE-DEMO-01') {
  const response = await api.get<WellLogSample[]>(`/api/v1/wells/${wellId}/logs?rows=180`);
  return response.data;
}

export async function analyzeSample(sample: WellLogSample) {
  const response = await api.post<AnalyticsResult>('/api/v1/analytics/sample', sample);
  return response.data;
}

export async function fetchAlerts() {
  const response = await api.get<Alert[]>('/api/v1/alerts');
  return response.data;
}

export async function fetchModelStatus() {
  const response = await api.get('/api/v1/monitoring/models');
  return response.data as {
    registered_models: string[];
    metrics: Record<string, number>;
    mlflow_tracking: string;
  };
}

