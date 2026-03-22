"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { API_BASE, authHeaders } from "@/lib/api";

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

  useEffect(() => {
    const raw = searchParams.get("plan") || "pro";
    const plan = VALID.has(raw) ? raw : "pro";
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/payments/create-checkout`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders(),
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
  }, [searchParams]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
        <div className="max-w-md space-y-4 text-center rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <p className="text-red-600 text-sm">{error}</p>
          <Link
            href="/dashboard"
            className="inline-block text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Volver al dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <p className="text-slate-600 text-sm">Redirigiendo a Stripe…</p>
    </div>
  );
}

export default function CreateCheckoutPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600 text-sm">
          Cargando…
        </div>
      }
    >
      <CheckoutRedirect />
    </Suspense>
  );
}
