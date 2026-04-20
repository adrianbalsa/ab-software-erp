"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Receipt } from "lucide-react";

import { FacturasDataTable } from "@/components/portal-cliente/FacturasDataTable";
import { PortalClienteAlert } from "@/components/portal-cliente/PortalClienteAlert";
import { PortalClienteEmptyState } from "@/components/portal-cliente/PortalClienteEmptyState";
import { SetupMandateCard } from "@/components/portal/SetupMandateCard";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { usePortalClienteOnboarding } from "@/context/PortalClienteOnboardingContext";
import { usePortalFacturas } from "@/hooks/usePortalCliente";
import { postPortalSetupMandate } from "@/lib/api";

export default function PortalClienteFacturasPage() {
  const { catalog } = useOptionalLocaleCatalog();
  const p = catalog.pages.portalClienteFacturas;
  const { refetch: refetchOnboarding, overview } = usePortalClienteOnboarding();
  const searchParams = useSearchParams();
  const router = useRouter();

  const { data, loading, error, refetch } = usePortalFacturas();
  const [mandateBusy, setMandateBusy] = useState(false);
  const [mandateErr, setMandateErr] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("setup") !== "success") return;
    void (async () => {
      await refetchOnboarding();
      router.replace("/portal-cliente/facturas");
    })();
  }, [searchParams, router, refetchOnboarding]);

  const hasActiveMandate = overview?.mandato_activo ?? false;

  const handleSetupMandate = useCallback(async () => {
    if (mandateBusy) return;
    setMandateBusy(true);
    setMandateErr(null);
    try {
      const out = await postPortalSetupMandate();
      if (out.has_active_mandate) {
        await refetchOnboarding();
        setMandateBusy(false);
        return;
      }
      if (!out.redirect_url?.trim()) {
        throw new Error(p.mandateNoRedirect);
      }
      window.location.href = out.redirect_url;
    } catch (e) {
      setMandateErr(e instanceof Error ? e.message : p.mandateStartError);
      setMandateBusy(false);
    }
  }, [mandateBusy, p.mandateNoRedirect, p.mandateStartError, refetchOnboarding]);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{p.title}</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{p.subtitle}</p>
      </div>

      <SetupMandateCard
        hasActiveMandate={hasActiveMandate}
        isLoading={mandateBusy}
        onSetup={handleSetupMandate}
        copy={p.mandate}
      />

      {mandateErr ? <PortalClienteAlert>{mandateErr}</PortalClienteAlert> : null}

      {error ? (
        <PortalClienteAlert>
          {error}
          <button
            type="button"
            className="ml-3 font-semibold underline"
            onClick={() => void refetch()}
          >
            {p.retry}
          </button>
        </PortalClienteAlert>
      ) : null}

      <section
        aria-busy={loading && data.length === 0}
        aria-live="polite"
        aria-label={loading && data.length === 0 ? p.loadingAria : undefined}
        className="space-y-4"
      >
        {loading && data.length === 0 ? (
          <p className="text-sm text-zinc-500" role="status">
            {p.loading}
          </p>
        ) : null}
        {!loading && data.length === 0 ? (
          <div className="rounded-xl border border-zinc-200/90 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-900/50">
            <PortalClienteEmptyState icon={Receipt} title={p.empty} description={p.emptyHint} />
          </div>
        ) : null}
        {!loading && data.length > 0 ? <FacturasDataTable rows={data} /> : null}
      </section>
    </div>
  );
}
