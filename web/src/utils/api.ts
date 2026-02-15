const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

export function forwardedApiHeaders(clientAddress?: string): HeadersInit | undefined {
  if (!clientAddress) return undefined;
  return { 'x-forwarded-for': clientAddress };
}
