"use client";

import { useEffect } from "react";
import { API_BASE } from "@/lib/api";

/**
 * Punto de entrada desde la landing: redirige al flujo OIDC Google del backend
 * (SessionMiddleware + state CSRF). Tras Google, el backend redirige a
 * {PUBLIC_APP_URL}/auth/callback?token=… con el JWT; esa página guarda la sesión y va al dashboard.
 */
export default function GoogleAuthEntryPage() {
  useEffect(() => {
    const base = API_BASE.replace(/\/$/, "");
    window.location.replace(`${base}/auth/oauth/google/login`);
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#f4f6fb] px-6">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-emerald-600" aria-hidden />
      <p className="text-sm font-medium text-zinc-600">Conectando con Google…</p>
      <p className="max-w-sm text-center text-xs text-zinc-500">
        Si no avanza, comprueba que OAuth esté configurado en el servidor o inicia sesión con usuario y contraseña.
      </p>
    </div>
  );
}
