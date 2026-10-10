import { getApiKey } from "./auth";

export interface DeviceStatus {
  online: boolean;
  power: boolean | null;
  mode: string | null;
  color: { h: number; s: number; v: number } | null;
}

export interface ParamSchema {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "slider";
  default: string | number | null;
  placeholder?: string;
  options?: { value: string | number; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
}

export interface EffectDef {
  name: string;
  label: string;
  description: string;
  params: ParamSchema[];
}

export interface EffectState {
  name: string;
  params: Record<string, unknown>;
}

export interface AppSettings {
  brightness: number;
  auto_on: string | null;
  auto_off: string | null;
  weather_lat: number;
  weather_lon: number;
}

/** Error carrying the HTTP status, so callers can detect 401 (auth). */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(path, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string> | undefined) },
  });

  if (res.status === 401) {
    throw new ApiError(401, "Unauthorized — an API key is required");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getStatus: () => request<DeviceStatus>("/api/status"),
  setPower: (on: boolean) =>
    request("/api/power", { method: "POST", body: JSON.stringify({ on }) }),

  getEffects: () => request<EffectDef[]>("/api/effects"),
  getCurrentEffect: () => request<EffectState | null>("/api/effect"),
  activateEffect: (name: string, params: Record<string, unknown>) =>
    request("/api/effect", {
      method: "POST",
      body: JSON.stringify({ name, params }),
    }),
  stopEffect: () => request("/api/effect", { method: "DELETE" }),

  getSettings: () => request<AppSettings>("/api/settings"),
  saveSettings: (s: AppSettings) =>
    request<AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(s),
    }),
};
