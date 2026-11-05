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

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const base = await apiBase();
  return fetch(`${base}${input}`, init);
}

/** Open a URL in the default browser, not inside the Tauri webview. */
export async function openExternal(url: string): Promise<void> {
  if (IS_TAURI) {
    await openUrl(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}
