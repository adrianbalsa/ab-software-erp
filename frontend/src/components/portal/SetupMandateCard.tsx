"use client";

import { Landmark, Loader2, ShieldCheck } from "lucide-react";

type SetupMandateCardProps = {
  hasActiveMandate: boolean;
  isLoading?: boolean;
  onSetup: () => void | Promise<void>;
};

export function SetupMandateCard({
  hasActiveMandate,
  isLoading = false,
  onSetup,
}: SetupMandateCardProps) {
  if (hasActiveMandate) {
    return (
      <section className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50/70 shadow-sm">
        <div className="flex items-start gap-3 px-5 py-4">
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="text-base font-semibold text-emerald-900">
              Domiciliación SEPA activa
            </h3>
            <p className="mt-1 text-sm text-emerald-800/90">
              Tu mandato está verificado y tus próximas facturas podrán cobrarse
              automáticamente de forma segura.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mb-5 rounded-2xl border border-zinc-200/90 bg-white shadow-sm">
      <div className="border-b border-zinc-100 bg-gradient-to-r from-emerald-50/80 to-zinc-50/50 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm">
            <Landmark className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="text-base font-semibold text-zinc-900">
              Automatizar Pagos (SEPA)
            </h3>
            <p className="text-sm text-zinc-600">
              Autoriza el cobro automático de tus facturas mediante GoCardless.
              Seguro, regulado y sin comisiones ocultas.
            </p>
          </div>
        </div>
      </div>
      <div className="px-5 py-4">
        <button
          type="button"
          onClick={() => void onSetup()}
          disabled={isLoading}
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Redirigiendo…
            </>
          ) : (
            <>
              <ShieldCheck className="h-4 w-4" aria-hidden />
              Configurar Domiciliación Segura
            </>
          )}
        </button>
      </div>
    </section>
  );
}

