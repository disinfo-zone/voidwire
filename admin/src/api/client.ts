export const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

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
  return new Error(detail ? `API error: ${res.status} - ${detail}` : `API error: ${res.status}`);
}

export async function apiGet(path: string) {
  const token = localStorage.getItem('voidwire_admin_token');
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPost(path: string, body?: unknown) {
  const token = localStorage.getItem('voidwire_admin_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPatch(path: string, body: unknown) {
  const token = localStorage.getItem('voidwire_admin_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiPut(path: string, body: unknown) {
  const token = localStorage.getItem('voidwire_admin_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}

export async function apiDelete(path: string) {
  const token = localStorage.getItem('voidwire_admin_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw await buildApiError(res);
  return res.json();
}
