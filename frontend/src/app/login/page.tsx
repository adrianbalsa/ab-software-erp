"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, LogIn } from "lucide-react";

import { API_BASE, jwtRbacRole, notifyJwtUpdated } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/presupuestos";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const t = localStorage.getItem("jwt_token");
      if (t) router.replace(redirectTo);
    } catch {
      /* ignore */
    }
  }, [router, redirectTo]);

  const login = async () => {
    setError(null);
    setBusy(true);
    try {
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : "Credenciales incorrectas",
        );
      }
      const data = await res.json();
      try {
        localStorage.setItem("jwt_token", data.access_token);
        notifyJwtUpdated();
      } catch {
        /* ignore */
      }
      const next =
        jwtRbacRole() === "cliente" ? "/portal" : redirectTo;
      router.replace(next);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error de conexión");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#f4f6fb] p-6">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200/90 bg-white p-8 shadow-[0_1px_3px_rgba(15,23,42,0.06)]">
        <div className="mb-6 flex items-center gap-2 text-slate-800">
          <Building2 className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-xl font-bold tracking-tight">AB Logistics OS</h1>
            <p className="text-sm text-slate-500">Inicia sesión en tu empresa</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">
              Usuario
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2.5 outline-none focus:ring-2 focus:ring-blue-500"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 p-2.5 outline-none focus:ring-2 focus:ring-blue-500"
              autoComplete="current-password"
            />
          </div>
          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}
          <button
            type="button"
            onClick={() => void login()}
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-zinc-700 via-zinc-800 to-emerald-600 py-3 font-bold text-white shadow-lg shadow-zinc-900/25 transition-all hover:brightness-105 disabled:opacity-60"
          >
            <LogIn className="h-5 w-5" />
            {busy ? "Entrando…" : "Iniciar sesión"}
          </button>

          <div className="relative py-2 text-center text-xs text-zinc-400">
            <span className="relative z-10 bg-white px-2">o continúa con</span>
            <span className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-zinc-200" aria-hidden />
          </div>

          <Link
            href="/auth/google"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-200 bg-white py-3 text-sm font-semibold text-zinc-800 shadow-sm transition-colors hover:border-emerald-300 hover:bg-emerald-50/80"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden>
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Google
          </Link>
        </div>

        <p className="mt-6 text-center text-sm text-slate-500">
          <Link href="/" className="font-medium text-blue-600 hover:text-blue-500">
            Volver al inicio
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500">
          Cargando…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
