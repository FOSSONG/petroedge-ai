import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "../api/http";
import type { LoginResponse } from "../api/types";

const ROLES_KEY = "petroedge_roles";

export function persistSession(response: LoginResponse): void {
  setAccessToken(response.access_token);
  localStorage.setItem(
    ROLES_KEY,
    JSON.stringify(response.roles ?? []),
  );
}

export function restoreSession(): {
  token: string | null;
  roles: string[];
} {
  const token = getAccessToken();

  try {
    const roles = JSON.parse(
      localStorage.getItem(ROLES_KEY) ?? "[]",
    ) as string[];

    return {
      token,
      roles: Array.isArray(roles) ? roles : [],
    };
  } catch {
    return { token, roles: [] };
  }
}

export function clearSession(): void {
  clearAccessToken();
  localStorage.removeItem(ROLES_KEY);
}
