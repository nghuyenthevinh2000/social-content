import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

export const IS_TAURI =
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

let basePromise: Promise<string> | null = null;

/** Empty string in browser dev; local sidecar URL inside Tauri. */
export function apiBase(): Promise<string> {
  if (!IS_TAURI) return Promise.resolve("");
  if (!basePromise) {
    basePromise = invoke<string>("api_base").catch(() => "");
  }
  return basePromise;
}

/** Stable per-browser id so the backend can queue and limit jobs per client. */
function clientId(): string {
  let id = localStorage.getItem("aibrand-client-id");
  if (!id) {
    id = crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("aibrand-client-id", id);
  }
  return id;
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const base = await apiBase();
  const headers = new Headers(init?.headers);
  headers.set("X-Client-Id", clientId());
  return fetch(`${base}${input}`, { ...init, headers });
}

/** Open a URL in the default browser, not inside the Tauri webview. */
export async function openExternal(url: string): Promise<void> {
  if (IS_TAURI) {
    await openUrl(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
