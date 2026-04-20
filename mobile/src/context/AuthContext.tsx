import * as SecureStore from "expo-secure-store";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setMemoryAccessToken } from "../lib/api";
import { loginWithPassword } from "../services/authApi";

const SECURE_KEY = "abl_access_token";

type AuthContextValue = {
  token: string | null;
  isReady: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let stored: string | null = null;
      try {
        stored = await SecureStore.getItemAsync(SECURE_KEY);
      } catch {
        stored = null;
      } finally {
        if (!cancelled) {
          setToken(stored);
          setMemoryAccessToken(stored);
          setIsReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const res = await loginWithPassword(username.trim(), password);
    await SecureStore.setItemAsync(SECURE_KEY, res.access_token);
    setMemoryAccessToken(res.access_token);
    setToken(res.access_token);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await SecureStore.deleteItemAsync(SECURE_KEY);
    } catch {
      /* clave inexistente en primer arranque */
    }
    setMemoryAccessToken(null);
    setToken(null);
  }, []);

  const value = useMemo(
    () => ({
      token,
      isReady,
      signIn,
      signOut,
    }),
    [token, isReady, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
