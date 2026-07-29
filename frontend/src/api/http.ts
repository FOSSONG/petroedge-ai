const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") ??
  "/api/v1";

const API_BASE_URL = configuredApiBaseUrl.startsWith("http")
  ? configuredApiBaseUrl
  : `${window.location.origin}${
      configuredApiBaseUrl.startsWith("/")
        ? configuredApiBaseUrl
        : `/${configuredApiBaseUrl}`
    }`;

const TOKEN_KEY = "petroedge_access_token";
const AUTH_EXPIRED_EVENT = "petroedge:auth-expired";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function notifyAuthenticationExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
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

function formatErrorMessage(
  detail: unknown,
  status: number,
): string {
  if (typeof detail === "string" && detail.trim()) {
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
): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);

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
      },
    );
  } catch (error) {
    throw new ApiError(
      "Cannot reach the PetroEdge API. Confirm that the backend is running.",
      0,
      error,
    );
  }

  const payload = await parseResponse(response);

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
    );
  }

  return payload as T;
}

export {
  API_BASE_URL,
  AUTH_EXPIRED_EVENT,
  TOKEN_KEY,
};

