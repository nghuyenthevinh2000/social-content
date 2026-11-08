import { auth } from './firebase';

/**
 * Browser-based API client for backend communication.
 * In dev mode, /api requests proxy to http://127.0.0.1:8765.
 */
function clientId(): string {
  let id = localStorage.getItem('aibrand-client-id');
  if (!id) {
    id = crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem('aibrand-client-id', id);
  }
  return id;
}

export async function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  headers.set('X-Client-Id', clientId());
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers.set('Authorization', `Bearer ${token}`);
      headers.set('X-User-Id', auth.currentUser.uid);
      if (auth.currentUser.email) {
        headers.set('X-User-Email', auth.currentUser.email);
      }
    } catch {
      // Proceed without token if refresh fails
    }
  }
  return fetch(input, { ...init, headers });
}

export async function apiJson<T = any>(input: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(input, init);
  const text = (await res.text()).trim();
  let data: any = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // Non-JSON response body
    }
  }
  if (!res.ok) {
    const message =
      data?.error ||
      (res.status === 502 || res.status === 504
        ? 'Không thể kết nối đến máy chủ backend (127.0.0.1:8765)'
        : `Máy chủ phản hồi lỗi (${res.status} ${res.statusText || 'Error'})`.trim());
    throw new Error(message);
  }
  return (data ?? {}) as T;
}
