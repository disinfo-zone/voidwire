const TOKEN_KEY = 'voidwire_token';
const CSRF_COOKIE_NAME = 'voidwire_csrf_token';
const CSRF_HEADER_NAME = 'x-csrf-token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const local = window.localStorage.getItem(TOKEN_KEY);
    if (local) return local;
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(_token: string): void {
  // Auth now relies on HttpOnly cookies set by the API.
  // Keep this function for backwards compatibility and cleanup.
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore storage access restrictions.
  }
}

export function clearToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Ignore storage access restrictions.
  }
}

function getCookie(name: string): string {
  if (typeof document === 'undefined') return '';
  const target = `${name}=`;
  for (const rawPart of document.cookie.split(';')) {
    const part = rawPart.trim();
    if (part.startsWith(target)) {
      return decodeURIComponent(part.slice(target.length));
    }
  }
  return '';
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const body = options.body;
  const method = String(options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const csrf = getCookie(CSRF_COOKIE_NAME);
    if (csrf) {
      headers.set(CSRF_HEADER_NAME, csrf);
    }
  }
  if (body !== undefined && body !== null && !(body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(path, { ...options, headers, credentials: 'include' });
}
