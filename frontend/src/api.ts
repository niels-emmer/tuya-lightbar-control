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

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text);
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
