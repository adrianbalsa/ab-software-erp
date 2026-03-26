"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, BadgeEuro, CalendarClock, CheckCircle2, FileCheck2 } from "lucide-react";

type RiskAssessmentCardProps = {
  score: number;
  creditLimitEur: number;
  collectionTerms: string;
  reasons: string[];
  onConfirm?: () => void;
  ctaLabel?: string;
  isLoading?: boolean;
};

type RiskVisualState = {
  label: string;
  tone: string;
  badgeClassName: string;
  panelClassName: string;
  icon: typeof CheckCircle2;
};

function getRiskVisualState(score: number): RiskVisualState {
  if (score < 4) {
    return {
      label: "Confianza Alta",
      tone: "Riesgo bajo",
      badgeClassName: "border-emerald-300 bg-emerald-50 text-emerald-800",
      panelClassName: "border-emerald-200 bg-emerald-50/40",
      icon: CheckCircle2,
    };
  }
  if (score <= 7) {
    return {
      label: "Riesgo Moderado",
      tone: "Revisión recomendada",
      badgeClassName: "border-amber-300 bg-amber-50 text-amber-900",
      panelClassName: "border-amber-200 bg-amber-50/40",
      icon: AlertTriangle,
    };
  }
  return {
    label: "Riesgo Alto",
    tone: "Aplicar cautelas",
    badgeClassName: "border-rose-300 bg-rose-50 text-rose-900",
    panelClassName: "border-rose-200 bg-rose-50/40",
    icon: AlertTriangle,
  };
}

function formatEUR(value: number): string {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function RiskAssessmentCard({
  score,
  creditLimitEur,
  collectionTerms,
  reasons,
  onConfirm,
  ctaLabel = "Confirmar y continuar",
  isLoading = false,
}: RiskAssessmentCardProps) {
  const [accepted, setAccepted] = useState(false);
  const safeScore = Number.isFinite(score) ? Math.min(10, Math.max(1, Math.round(score))) : 1;
  const visual = useMemo(() => getRiskVisualState(safeScore), [safeScore]);
  const StatusIcon = visual.icon;

  return (
    <section className="w-full rounded-2xl border border-zinc-300 bg-white p-6 shadow-sm sm:p-8">
      <header className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">Informe de Riesgo Financiero</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-xl font-semibold text-zinc-900 sm:text-2xl">Evaluación de Alta Comercial</h3>
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${visual.badgeClassName}`}>
            <StatusIcon className="h-4 w-4" />
            {visual.label}
          </span>
        </div>
      </header>

      <div className={`mt-5 rounded-xl border p-4 ${visual.panelClassName}`}>
        <p className="text-sm text-zinc-700">
          Score de riesgo: <span className="font-semibold text-zinc-900">{safeScore}/10</span>
        </p>
        <p className="mt-1 text-sm text-zinc-600">{visual.tone}</p>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            <BadgeEuro className="h-4 w-4" />
            Límite de crédito
          </p>
          <p className="mt-2 text-lg font-semibold text-zinc-900">{formatEUR(creditLimitEur)}</p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
            <CalendarClock className="h-4 w-4" />
            Plazo de cobro
          </p>
          <p className="mt-2 text-sm font-medium text-zinc-900">{collectionTerms}</p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Motivos de evaluación</p>
        <ul className="mt-3 space-y-2">
          {reasons.map((reason, idx) => (
            <li key={`${reason}-${idx}`} className="flex items-start gap-2 text-sm text-zinc-700">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-500" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-6 rounded-xl border border-zinc-300 bg-zinc-50 p-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-zinc-400 text-zinc-900 focus:ring-zinc-500"
            aria-required="true"
          />
          <span className="text-sm leading-relaxed text-zinc-700">
            Acepto mi evaluacion de riesgo y el sistema de cobro automatico SEPA como condicion para operar.
          </span>
        </label>
      </div>

      <div className="mt-6 flex items-center justify-end">
        <button
          type="button"
          disabled={!accepted || isLoading}
          onClick={onConfirm}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-900 bg-zinc-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:border-zinc-300 disabled:bg-zinc-200 disabled:text-zinc-500"
        >
          <FileCheck2 className="h-4 w-4" />
          {ctaLabel}
        </button>
      </div>
    </section>
  );
}

