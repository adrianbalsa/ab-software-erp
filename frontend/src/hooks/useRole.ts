"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ABL_JWT_UPDATED_EVENT,
  jwtRbacRole,
  type AppRbacRole,
} from "@/lib/api";

export function useRole(): {
  role: AppRbacRole;
  /** Renueva el rol leyendo el JWT actual (tras login/refresh). */
  refresh: () => void;
} {
  const [role, setRole] = useState<AppRbacRole>(() =>
    typeof window !== "undefined" ? jwtRbacRole() : "driver"
  );

  const refresh = useCallback(() => {
    setRole(jwtRbacRole());
  }, []);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "jwt_token" || e.key === null) refresh();
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

  return { role, refresh };
}
