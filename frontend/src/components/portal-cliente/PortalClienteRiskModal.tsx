"use client";

import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";

import RiskAssessmentCard from "@/components/auth/RiskAssessmentCard";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { usePortalClienteOnboarding } from "@/context/PortalClienteOnboardingContext";
import { Button } from "@/components/ui/button";

export function PortalClienteRiskModal() {
  const { loading, error, overview, refetch, acceptRisk, acceptLoading } = usePortalClienteOnboarding();
  const { catalog, locale } = useOptionalLocaleCatalog();
  const t = catalog.pages.portalClienteRisk;
  const formatLocale = locale === "en" ? "en-GB" : "es-ES";
  const panelRef = useRef<HTMLDivElement>(null);

  const needsBlock = !loading && overview && !overview.riesgo_aceptado;
  const showOverlay = loading || !!error || needsBlock;

  useEffect(() => {
    if (!showOverlay) return undefined;
    const id = window.requestAnimationFrame(() => {
      const root = panelRef.current;
      if (!root) return;
      if (loading) return;
      if (error) {
        root.querySelector<HTMLButtonElement>("button[type='button']")?.focus();
        return;
      }
      if (needsBlock) {
        root.querySelector<HTMLInputElement>("input[type='checkbox']")?.focus();
      }
    });
    return () => window.cancelAnimationFrame(id);
  }, [showOverlay, loading, error, needsBlock]);

  if (!showOverlay) return null;

  const describedBy =
    !loading && !error && needsBlock ? "portal-risk-desc" : error ? "portal-risk-error-detail" : undefined;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="portal-risk-dialog-title"
      aria-describedby={describedBy}
      aria-busy={loading}
    >
      <div
        ref={panelRef}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-xl outline-none dark:bg-zinc-900 sm:p-6"
        tabIndex={-1}
      >
        {loading && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-zinc-600 dark:text-zinc-300">
            <Loader2 className="h-8 w-8 animate-spin text-zinc-500" aria-hidden />
            <p className="text-sm font-medium" role="status" aria-live="polite">
              {t.loading}
            </p>
          </div>
        )}

        {!loading && error && (
          <div className="space-y-4 py-4">
            <p id="portal-risk-dialog-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {t.loadError}
            </p>
            <p id="portal-risk-error-detail" className="text-sm text-red-700 dark:text-red-300">
              {error}
            </p>
            <Button type="button" variant="outline" onClick={() => void refetch()}>
              {t.retry}
            </Button>
          </div>
        )}

        {!loading && !error && overview && !overview.riesgo_aceptado && (
          <div className="space-y-2">
            <h2 id="portal-risk-dialog-title" className="sr-only">
              {t.riskCard.title}
            </h2>
            <p id="portal-risk-desc" className="sr-only">
              {t.dialogIntro}
            </p>
            <RiskAssessmentCard
              score={overview.score}
              creditLimitEur={overview.creditLimitEur}
              collectionTerms={overview.collectionTerms}
              reasons={overview.reasons?.length ? overview.reasons : ["—"]}
              onConfirm={() => void acceptRisk()}
              ctaLabel={acceptLoading ? t.acceptPending : undefined}
              isLoading={acceptLoading}
              copy={t.riskCard}
              formatLocale={formatLocale}
            />
          </div>
        )}
      </div>
    </div>
  );
}
