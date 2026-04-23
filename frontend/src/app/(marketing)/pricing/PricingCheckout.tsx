"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";

function priceEnv() {
  return {
    basic: (process.env.NEXT_PUBLIC_STRIPE_PRICE_BASIC ?? "").trim(),
    enterprise: (process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE ?? "").trim(),
  };
}

export function PricingCheckout() {
  const searchParams = useSearchParams();
  const empresaId = (searchParams.get("empresa_id") ?? "").trim();
  const [loadingPriceId, setLoadingPriceId] = useState<string | null>(null);

  const { basicId, enterpriseId, ready } = useMemo(() => {
    const ids = priceEnv();
    return {
      basicId: ids.basic,
      enterpriseId: ids.enterprise,
      ready: Boolean(ids.basic && ids.enterprise),
    };
  }, []);

  const startCheckout = async (priceId: string) => {
    if (!priceId) {
      toast.error("Falta configurar los precios de Stripe (variables NEXT_PUBLIC_*).");
      return;
    }
    if (!empresaId) {
      toast.error(
        "Falta el identificador de empresa. Usa el enlace de alta o añade ?empresa_id=TU_UUID en la URL.",
      );
      return;
    }
    setLoadingPriceId(priceId);
    try {
      const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
      const response = await apiFetch(`${apiUrl}/api/v1/stripe/crear-sesion-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ price_id: priceId, empresa_id: empresaId }),
      });
      const data = (await response.json()) as { url?: string; detail?: unknown };
      if (!response.ok) {
        const msg =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x))).join(" ")
              : "No se pudo iniciar el pago";
        toast.error(msg);
        return;
      }
      if (data.url) {
        window.location.href = data.url;
        return;
      }
      toast.error("Respuesta sin URL de Stripe.");
    } catch {
      toast.error("Error de conexión con la pasarela de pago.");
    } finally {
      setLoadingPriceId(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">Planes y cobro</h1>
        <p className="mt-3 text-sm text-zinc-400 sm:text-base">
          Elige Basic o Enterprise. Necesitas el UUID de tu empresa en la URL{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-200">?empresa_id=…</code> (enlace de
          onboarding o administrador).
        </p>
        {!empresaId ? (
          <p className="mt-4 text-sm text-amber-200/90">
            Sin <span className="font-mono text-amber-100">empresa_id</span> no se puede asociar el pago a tu
            cuenta.
          </p>
        ) : null}
        {!ready ? (
          <p className="mt-6 rounded-xl border border-amber-500/30 bg-amber-950/40 px-4 py-3 text-left text-sm text-amber-100">
            Configura en el build <span className="font-mono">NEXT_PUBLIC_STRIPE_PRICE_BASIC</span> y{" "}
            <span className="font-mono">NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE</span> con los Price ID de Stripe.
          </p>
        ) : null}
      </div>

      <div className="mt-14 grid gap-8 sm:grid-cols-2">
        <div className="flex flex-col rounded-3xl border border-zinc-800 bg-zinc-900/70 p-8">
          <h2 className="text-lg font-semibold text-white">Basic</h2>
          <p className="mt-2 text-sm text-zinc-400">VeriFactu, CMR digital y operativa esencial.</p>
          <button
            type="button"
            disabled={!basicId || !ready || loadingPriceId === basicId}
            onClick={() => void startCheckout(basicId)}
            className="mt-8 inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-zinc-600 px-4 py-3 text-sm font-semibold text-zinc-100 transition hover:bg-zinc-800 disabled:opacity-50"
          >
            {loadingPriceId === basicId ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Conectando…
              </>
            ) : (
              "Contratar Basic"
            )}
          </button>
        </div>

        <div className="relative flex flex-col rounded-3xl border border-emerald-500/40 bg-gradient-to-b from-emerald-500/10 to-zinc-900/90 p-8 ring-1 ring-emerald-500/25">
          <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-bold uppercase tracking-wide text-zinc-950">
            Enterprise
          </span>
          <h2 className="text-lg font-semibold text-white">Enterprise</h2>
          <p className="mt-2 text-sm text-zinc-400">ESG, portal B2B y módulos avanzados.</p>
          <button
            type="button"
            disabled={!enterpriseId || !ready || loadingPriceId === enterpriseId}
            onClick={() => void startCheckout(enterpriseId)}
            className="mt-8 inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-emerald-500 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-50"
          >
            {loadingPriceId === enterpriseId ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Conectando…
              </>
            ) : (
              "Contratar Enterprise"
            )}
          </button>
        </div>
      </div>

      <p className="mt-12 text-center text-sm text-zinc-500">
        <Link href="/" className="text-emerald-400 hover:text-emerald-300">
          Volver al inicio
        </Link>
      </p>
    </div>
  );
}
