"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, KeyRound, Loader2, ShieldCheck } from "lucide-react";

import { getSupabaseBrowserClient } from "@/lib/supabase";

function readHashParams(): URLSearchParams {
  if (typeof window === "undefined") return new URLSearchParams();
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  return new URLSearchParams(hash);
}

function SetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const minLengthOk = password.length >= 8;
  const matchOk = password.length > 0 && password === confirmPassword;
  const canSubmit = minLengthOk && matchOk && !busy && sessionReady;

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      setSessionError("Configuración pendiente. Contacta con soporte.");
      return;
    }

    async function bootstrapRecoverySession() {
      if (!supabase) return;
      try {
        const fromSearchToken =
          searchParams.get("token_hash") ||
          searchParams.get("token") ||
          searchParams.get("code");
        if (fromSearchToken) {
          setSessionReady(true);
          return;
        }

        const hashParams = readHashParams();
        const accessToken = hashParams.get("access_token");
        const refreshToken = hashParams.get("refresh_token");
        if (accessToken && refreshToken) {
          const { error } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });
          if (error) throw error;
        }
        setSessionReady(true);
      } catch (e) {
        setSessionError(
          e instanceof Error
            ? e.message
            : "No se pudo validar el enlace de recuperacion.",
        );
      }
    }

    void bootstrapRecoverySession();
  }, [searchParams]);

  const helperText = useMemo(() => {
    if (!minLengthOk) return "La contraseña debe tener al menos 8 caracteres.";
    if (!matchOk) return "Las contraseñas deben coincidir.";
    return "Credenciales validas para continuar.";
  }, [minLengthOk, matchOk]);

  const onSubmit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const supabase = getSupabaseBrowserClient();
      if (!supabase) {
        throw new Error("Configuración pendiente. Contacta con soporte.");
      }
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      router.replace("/portal-cliente/facturas");
    } catch (e) {
      setSubmitError(
        e instanceof Error ? e.message : "No se pudo actualizar la contraseña.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-2.5">
            <KeyRound className="h-5 w-5 text-zinc-700" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-zinc-900">Establecer Contraseña</h1>
            <p className="text-sm text-zinc-600">Define tu credencial de acceso al portal.</p>
          </div>
        </div>

        {sessionError ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {sessionError}
          </p>
        ) : null}
        {submitError ? (
          <p className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {submitError}
          </p>
        ) : null}

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-700">Nueva contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-zinc-400 focus:ring-2 focus:ring-zinc-300"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-700">Confirmar contraseña</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full rounded-lg border border-zinc-300 px-3 py-2.5 text-sm outline-none focus:border-zinc-400 focus:ring-2 focus:ring-zinc-300"
            />
          </div>
        </div>

        <p
          className={`mt-3 flex items-center gap-2 text-xs ${
            minLengthOk && matchOk ? "text-emerald-700" : "text-amber-700"
          }`}
        >
          {minLengthOk && matchOk ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <ShieldCheck className="h-4 w-4" />
          )}
          {helperText}
        </p>

        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={!canSubmit}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-zinc-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Guardar y Continuar
        </button>
      </section>
    </main>
  );
}

export default function SetPasswordPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
          <Loader2 className="h-8 w-8 animate-spin text-zinc-500" />
        </main>
      }
    >
      <SetPasswordContent />
    </Suspense>
  );
}
