/**
 * Browser-based API client for backend communication.
 * In dev mode, /api requests proxy to http://127.0.0.1:8765.
 */
function clientId(): string {
  let id = localStorage.getItem("aibrand-client-id");
  if (!id) {
    id = crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("aibrand-client-id", id);
  }
  return id;
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set("X-Client-Id", clientId());
  return fetch(input, { ...init, headers });
}
