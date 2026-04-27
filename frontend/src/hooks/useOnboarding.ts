"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "abl_onboarding_owner_tour_v1";

/**
 * Estado del tour de bienvenida (owner).
 * Persistencia en localStorage para no repetir en cada sesión.
 * (Perfil Supabase: ampliar con PATCH /perfil si se expone flag `onboarding_done`.)
 */
export function useOnboarding() {
  const [completed, setCompleted] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let nextCompleted = false;
    try {
      nextCompleted = localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      nextCompleted = false;
    }
    queueMicrotask(() => {
      setCompleted(nextCompleted);
      setHydrated(true);
    });
  }, []);

  const markComplete = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setCompleted(true);
  }, []);

  /** Solo desarrollo / soporte: volver a mostrar el tour. */
  const resetTour = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setCompleted(false);
  }, []);

  return {
    completed,
    hydrated,
    markComplete,
    resetTour,
  };
}
