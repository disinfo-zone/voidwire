import { useCallback, useEffect, useState } from 'react';
import { apiGet, apiPost } from '../api/client';

const SESSION_KEY = 'voidwire_admin_session';

function readSessionFlag(): boolean {
  try {
    return localStorage.getItem(SESSION_KEY) === '1';
  } catch {
    return false;
  }
}

function writeSessionFlag(value: boolean): void {
  try {
    if (value) {
      localStorage.setItem(SESSION_KEY, '1');
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    // Ignore storage access issues.
  }
}

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => readSessionFlag());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    apiGet('/admin/auth/me')
      .then(() => {
        if (!active) return;
        writeSessionFlag(true);
        setIsAuthenticated(true);
      })
      .catch(() => {
        if (!active) return;
        writeSessionFlag(false);
        setIsAuthenticated(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const setAuthenticated = useCallback((authenticated: boolean) => {
    writeSessionFlag(authenticated);
    setIsAuthenticated(authenticated);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiPost('/admin/auth/logout', {});
    } catch {
      // Best-effort logout.
    }
    setAuthenticated(false);
    if (typeof window !== 'undefined') {
      window.location.assign('/admin/login');
    }
  }, [setAuthenticated]);

  return { isAuthenticated, loading, setAuthenticated, logout };
}
