export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
const ADMIN_SESSION_KEY = 'voidwire_admin_session';
const CSRF_COOKIE_NAME = 'voidwire_csrf_token';
const CSRF_HEADER_NAME = 'x-csrf-token';

function getCookie(name: string): string {
  if (typeof document === 'undefined') return '';
  const target = `${name}=`;
  const parts = document.cookie.split(';');
  for (const rawPart of parts) {
    const part = rawPart.trim();
    if (part.startsWith(target)) {
      return decodeURIComponent(part.slice(target.length));
    }
  }
  return '';
}

function mutationHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const csrf = getCookie(CSRF_COOKIE_NAME);
  if (csrf) {
    headers[CSRF_HEADER_NAME] = csrf;
  }
  return headers;
}

async function buildApiError(res: Response): Promise<Error> {
  let detail = '';
  try {
    const payload = await res.clone().json();
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      detail = payload.detail.trim();
    }
  } catch {
    try {
      const text = (await res.text()).trim();
      if (text) detail = text;
    } catch {
      // Ignore parse errors and fall back to status-only message.
    }
  }
  if (res.status === 401) {
    localStorage.removeItem(ADMIN_SESSION_KEY);
  }
  return new Error(detail ? `API error: ${res.status} - ${detail}` : `API error: ${res.status}`);
}

export async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPost(path: string, body?: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: mutationHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPatch(path: string, body: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: mutationHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPut(path: string, body: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    credentials: 'include',
    headers: mutationHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiDelete(path: string) {
  const headers: Record<string, string> = {};
  const csrf = getCookie(CSRF_COOKIE_NAME);
  if (csrf) {
    headers[CSRF_HEADER_NAME] = csrf;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    credentials: 'include',
    headers,
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}
