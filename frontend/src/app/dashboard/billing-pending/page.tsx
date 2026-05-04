"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { Loader2 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { fetchEmpresaQuotaGate } from "@/lib/postAuthNavigation";

export default function BillingPendingPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const recheck = useCallback(async () => {
    setChecking(true);
    setHint(null);
    try {
      const gate = await fetchEmpresaQuotaGate();
      if (!gate) {
        setHint("No se pudo comprobar el estado. Inténtalo de nuevo.");
        return;
      }
      if (!gate.must_complete_checkout) {
        router.replace("/dashboard");
        router.refresh();
        return;
      }
      setHint("La suscripción sigue pendiente. El administrador debe completar el pago en Stripe.");
    } finally {
      setChecking(false);
    }
  }, [router]);

  return (
    <AppShell active="dashboard">
      <main className="flex min-h-0 flex-1 flex-col items-center justify-center bg-zinc-950 px-6 py-16">
        <div className="max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 text-center shadow-lg">
          <h1 className="text-lg font-semibold text-zinc-100">Suscripción pendiente</h1>
          <p className="mt-3 text-sm leading-relaxed text-zinc-400">
            El administrador de tu empresa debe completar el pago en Stripe antes de que el equipo pueda
            operar con normalidad en la plataforma.
          </p>
          <p className="mt-3 text-xs text-zinc-500">
            Si ya se ha pagado, el alta puede tardar unos segundos mientras se confirma con el banco.
          </p>
          {hint ? <p className="mt-4 text-xs text-amber-200/90">{hint}</p> : null}
          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
            <button
              type="button"
              disabled={checking}
              onClick={() => void recheck()}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-950/40 px-4 py-2.5 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-900/50 disabled:opacity-50"
            >
              {checking ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Comprobando…
                </>
              ) : (
                "Ya hemos pagado — comprobar"
              )}
            </button>
            <Link
              href="/dashboard/settings/billing"
              className="inline-flex justify-center rounded-xl border border-zinc-600 bg-zinc-800/60 px-4 py-2.5 text-sm font-semibold text-zinc-200 transition hover:border-zinc-500"
            >
              Ir a facturación
            </Link>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
