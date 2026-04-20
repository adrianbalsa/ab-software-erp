"use client";

import { Landmark, Loader2, ShieldCheck } from "lucide-react";

import type { Catalog } from "@/i18n/catalog";

type MandateCopy = Catalog["pages"]["portalClienteFacturas"]["mandate"];

type SetupMandateCardProps = {
  hasActiveMandate: boolean;
  isLoading?: boolean;
  onSetup: () => void | Promise<void>;
  copy: MandateCopy;
};

export function SetupMandateCard({
  hasActiveMandate,
  isLoading = false,
  onSetup,
  copy,
}: SetupMandateCardProps) {
  if (hasActiveMandate) {
    return (
      <section
        className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50/70 shadow-sm"
        aria-labelledby="mandate-sepa-title"
      >
        <div className="flex items-start gap-3 px-5 py-4">
          <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 id="mandate-sepa-title" className="text-base font-semibold text-emerald-900">
              {copy.activeTitle}
            </h3>
            <p className="mt-1 text-sm text-emerald-800/90">{copy.activeBody}</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      className="mb-5 rounded-2xl border border-zinc-200/90 bg-white shadow-sm"
      aria-labelledby="mandate-setup-title"
      aria-busy={isLoading}
    >
      <div className="border-b border-zinc-100 bg-gradient-to-r from-emerald-50/80 to-zinc-50/50 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm">
            <Landmark className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 id="mandate-setup-title" className="text-base font-semibold text-zinc-900">
              {copy.setupTitle}
            </h3>
            <p className="text-sm text-zinc-600">{copy.setupBody}</p>
          </div>
        </div>
      </div>
      <div className="px-5 py-4">
        <button
          type="button"
          onClick={() => void onSetup()}
          disabled={isLoading}
          aria-busy={isLoading}
          className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {copy.redirecting}
            </>
          ) : (
            <>
              <ShieldCheck className="h-4 w-4" aria-hidden />
              {copy.configureBtn}
            </>
          )}
        </button>
      </div>
    </section>
  );
}

