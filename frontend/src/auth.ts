// API key storage — kept in localStorage so it is never baked into the
// public JS bundle. Sent by api.ts as the X-API-Key header.

const STORAGE_KEY = "lightbar-api-key";

export function getApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* localStorage unavailable (private mode) — ignore */
  }
}

export function hasApiKey(): boolean {
  return getApiKey().length > 0;
}
