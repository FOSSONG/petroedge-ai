const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") ??
  "http://127.0.0.1:8000/api/v1";

const TOKEN_KEY = "petroedge_access_token";
const AUTH_EXPIRED_EVENT = "petroedge:auth-expired";
const DEFAULT_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  readonly requestId: string | null;

  constructor(
    message: string,
    status: number,
    detail?: unknown,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }
}

export function getAccessToken(): string | null {
  return (
    localStorage.getItem(TOKEN_KEY) ??
    sessionStorage.getItem(TOKEN_KEY)
  );
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

function notifyAuthenticationExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.toLowerCase().includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  try {
    return await response.text();
  } catch {
    return null;
  }
}

function extractErrorDetail(payload: unknown): unknown {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload
  ) {
    return (payload as { detail?: unknown }).detail;
  }

  return payload;
}

function formatErrorMessage(detail: unknown, status: number): string {
  if (status === 413) {
    return "The selected file exceeds the configured upload limit.";
  }

  if (typeof detail === "string" && detail.trim()) {
    if (detail.trim().toLowerCase().startsWith("<html")) {
      return `The server rejected the request with HTTP ${status}.`;
    }

    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof (item as { msg?: unknown }).msg === "string"
        ) {
          return (item as { msg: string }).msg;
        }

        return null;
      })
      .filter((value): value is string => Boolean(value));

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  return `Request failed with status ${status}.`;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`,
      {
        ...options,
        headers,
        signal: options.signal ?? controller.signal,
      },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "The PetroEdge request timed out.",
        0,
        error,
      );
    }

    throw new ApiError(
      "Cannot reach the PetroEdge API. Confirm that Docker Desktop and the backend are running.",
      0,
      error,
    );
  } finally {
    window.clearTimeout(timeout);
  }

  const payload = await parseResponse(response);
  const requestId = response.headers.get("X-Request-ID");

  if (!response.ok) {
    const detail = extractErrorDetail(payload);

    if (response.status === 401) {
      clearAccessToken();
      notifyAuthenticationExpired();
    }

    throw new ApiError(
      formatErrorMessage(detail, response.status),
      response.status,
      detail,
      requestId,
    );
  }

  return payload as T;
}

export {
  API_BASE_URL,
  AUTH_EXPIRED_EVENT,
  TOKEN_KEY,
};