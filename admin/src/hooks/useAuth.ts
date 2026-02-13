import { useState, useCallback } from 'react';

const TOKEN_KEY = 'voidwire_admin_token';

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY)
  );

  const setToken = useCallback((newToken: string | null) => {
    if (newToken) {
      localStorage.setItem(TOKEN_KEY, newToken);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
    setTokenState(newToken);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
  }, [setToken]);

  return { token, setToken, logout };
}
