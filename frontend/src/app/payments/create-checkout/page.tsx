"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { API_BASE, apiFetch } from "@/lib/api";

const VALID = new Set(["starter", "pro", "enterprise"]);

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
      .join(" ");
  }
  return "Error al iniciar el pago";
}

function CheckoutRedirect() {
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const source = searchParams.get("source");
  const fromOnboarding = source === "onboarding";
  const fromResume = source === "resume";

  const plan = useMemo(() => {
    const raw = searchParams.get("plan") || "starter";
    return VALID.has(raw) ? raw : "starter";
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/payments/create-checkout`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ plan_type: plan }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          if (!cancelled) setError(detailMessage(err?.detail) || `HTTP ${res.status}`);
          return;
        }
        const data = (await res.json()) as { url?: string };
        if (data.url) {
          window.location.href = data.url;
          return;
        }
        if (!cancelled) setError("Respuesta sin URL de pago");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [plan]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-6">
        <div className="max-w-md space-y-5 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-900/80 p-8 text-center shadow-xl">
          <p className="text-sm leading-relaxed text-rose-300">{error}</p>
          <p className="text-xs text-zinc-500">
            Si el pago no está disponible en este entorno, contacta con soporte o revisa la configuración de
            Stripe en el servidor.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Link
              href={`/payments/create-checkout?plan=${encodeURIComponent(plan)}${source ? `&source=${encodeURIComponent(source)}` : ""}`}
              className="inline-flex justify-center rounded-xl border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-900/50"
            >
              Reintentar
            </Link>
            <Link
              href="/dashboard/settings/billing"
              className="inline-flex justify-center rounded-xl border border-zinc-600 bg-zinc-800/60 px-4 py-2.5 text-sm font-semibold text-zinc-800 dark:text-zinc-200 transition hover:border-zinc-500"
            >
              Ir a facturación
            </Link>
            <Link href="/dashboard" className="inline-flex justify-center text-sm font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-800 dark:text-zinc-200">
              Volver al panel
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 dark:bg-zinc-950 px-6 text-center">
      <div
        className="h-9 w-9 animate-spin rounded-full border-2 border-zinc-600 border-t-emerald-500"
        aria-hidden
      />
      <div className="max-w-sm space-y-2">
        <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Abriendo Stripe…</p>
        <p className="text-xs leading-relaxed text-zinc-500">
          {fromOnboarding
            ? "Tras el alta de empresa, activa tu suscripción en la pasarela segura. No guardamos tu tarjeta en nuestros servidores."
            : fromResume
              ? "Falta activar la suscripción de tu espacio de trabajo. Un pago y podréis operar con normalidad."
              : "Serás redirigido a la pasarela segura de Stripe para completar la suscripción."}
        </p>
      </div>
    </div>
  );
}

export default function CreateCheckoutPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-sm text-zinc-500">
          Cargando…
        </div>
      }
    >
      <CheckoutRedirect />
    </Suspense>
  );
}
