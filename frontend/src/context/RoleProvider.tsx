"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  ABL_JWT_UPDATED_EVENT,
  jwtRbacRole,
  type AppRbacRole,
} from "@/lib/api";
import { AUTH_TOKEN_KEY } from "@/lib/auth";

type RoleContextValue = {
  role: AppRbacRole;
  refresh: () => void;
};

const RoleContext = createContext<RoleContextValue | null>(null);

type Props = {
  children: ReactNode;
  /** Rol resuelto en el servidor desde `abl_auth_token` o sesión Supabase (evita fallback "driver" en el primer paint). */
  initialRole?: AppRbacRole;
};

export function RoleProvider({ initialRole, children }: Props) {
  const [role, setRole] = useState<AppRbacRole>(() =>
    initialRole !== undefined ? initialRole : "driver",
  );

  const refresh = useCallback(() => {
    setRole(jwtRbacRole());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === AUTH_TOKEN_KEY || e.key === "jwt_token" || e.key === null) refresh();
    };
    window.addEventListener("storage", onStorage);

    const onJwt = () => refresh();
    window.addEventListener(ABL_JWT_UPDATED_EVENT, onJwt);

    const onFocus = () => refresh();
    window.addEventListener("focus", onFocus);

    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(ABL_JWT_UPDATED_EVENT, onJwt);
      window.removeEventListener("focus", onFocus);
    };
  }, [refresh]);

  return (
    <RoleContext.Provider value={{ role, refresh }}>{children}</RoleContext.Provider>
  );
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) {
    throw new Error("useRole debe usarse dentro de RoleProvider");
  }
  return ctx;
}
