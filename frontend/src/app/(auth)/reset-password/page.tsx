"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as Sentry from "@sentry/nextjs";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_BASE, apiFetch, parseApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

function ResetPasswordFallback() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0c0a09] px-4 py-12 text-stone-100">
      <p className="text-sm text-stone-400">Cargando…</p>
    </main>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useMemo(() => (searchParams.get("token") || "").trim(), [searchParams]);

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = useCallback(() => {
    if (password.length < 8) {
      setFieldError("La contraseña debe tener al menos 8 caracteres.");
      return false;
    }
    if (password !== confirm) {
      setFieldError("Las contraseñas no coinciden.");
      return false;
    }
    setFieldError(null);
    return true;
  }, [password, confirm]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setFieldError("Enlace inválido o incompleto. Solicita un nuevo correo de recuperación.");
      return;
    }
    if (!validate()) return;

    setSubmitting(true);
    setFieldError(null);
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (!res.ok) {
        const msg = await parseApiError(res);
        throw new Error(msg);
      }
      router.replace("/login?password_reset=success");
    } catch (err) {
      const message = err instanceof Error ? err.message : "No se pudo actualizar la contraseña.";
      Sentry.captureException(err instanceof Error ? err : new Error(String(err)), {
        tags: { flow: "reset_password" },
        extra: { hasToken: Boolean(token) },
      });
      setFieldError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#0c0a09] px-4 py-12 text-stone-100">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.07]"
        style={{
          backgroundImage: `radial-gradient(circle at 20% 20%, #14b8a6 0%, transparent 45%),
            radial-gradient(circle at 80% 10%, #0d9488 0%, transparent 40%),
            radial-gradient(circle at 50% 80%, #115e59 0%, transparent 50%)`,
        }}
        aria-hidden
      />
      <section
        className={cn(
          "relative z-10 w-full max-w-md rounded-2xl border border-teal-500/25 bg-stone-900/90 p-8 shadow-[0_0_0_1px_rgba(20,184,166,0.08),0_24px_48px_rgba(0,0,0,0.45)]",
          "backdrop-blur-sm",
        )}
      >
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Image src="/logo.png" alt="AB Logistics OS" width={56} height={56} className="h-14 w-14 object-contain" />
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-teal-400/90">Seguridad</p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-stone-50">Nueva contraseña</h1>
            <p className="mt-2 text-sm text-stone-400">
              Elige una contraseña segura. El enlace caduca si pasó demasiado tiempo.
            </p>
          </div>
        </div>

        {!token ? (
          <p className="rounded-lg border border-amber-500/30 bg-amber-950/40 px-3 py-2 text-sm text-amber-100">
            Falta el token en la URL. Abre el enlace del correo o solicita uno nuevo desde el inicio de sesión.
          </p>
        ) : null}

        <form onSubmit={(e) => void onSubmit(e)} className="mt-6 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="new-password" className="text-sm font-medium text-stone-300">
              Nueva contraseña
            </label>
            <Input
              id="new-password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting || !token}
              className="h-11 border-teal-500/25 bg-stone-950/80 text-stone-100 placeholder:text-stone-500 focus-visible:border-teal-400/60 focus-visible:ring-teal-500/30"
              placeholder="Mínimo 8 caracteres"
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="confirm-password" className="text-sm font-medium text-stone-300">
              Confirmar contraseña
            </label>
            <Input
              id="confirm-password"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              disabled={submitting || !token}
              className="h-11 border-teal-500/25 bg-stone-950/80 text-stone-100 placeholder:text-stone-500 focus-visible:border-teal-400/60 focus-visible:ring-teal-500/30"
              placeholder="Repite la contraseña"
            />
          </div>

          {fieldError ? (
            <p className="rounded-lg border border-rose-500/30 bg-rose-950/35 px-3 py-2 text-sm text-rose-100">
              {fieldError}
            </p>
          ) : null}

          <Button
            type="submit"
            disabled={submitting || !token}
            className="h-11 w-full border border-teal-400/30 bg-teal-600 text-white shadow-[0_0_20px_rgba(13,148,136,0.25)] hover:bg-teal-500 disabled:opacity-50"
          >
            {submitting ? "Actualizando…" : "Actualizar contraseña"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-stone-500">
          <Link href="/login" className="text-teal-400/90 underline-offset-4 hover:text-teal-300 hover:underline">
            Volver al inicio de sesión
          </Link>
        </p>
      </section>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordFallback />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
