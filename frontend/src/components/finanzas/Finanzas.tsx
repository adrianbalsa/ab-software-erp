"use client";

import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Gauge, Landmark, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { formatCurrencyEUR } from "@/i18n/localeFormat";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";

export function Finanzas() {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages;
  const fmtEur = (n: number) => formatCurrencyEUR(n, locale);

  const { data, loading, error, refresh } = useFinanceDashboard();

  useEffect(() => {
    const timer = window.setInterval(() => void refresh(), 20_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const chartData =
    data?.ingresos_vs_gastos_mensual.map((r) => ({
      periodo: r.periodo,
      ingresos: r.ingresos,
      gastos: r.gastos,
    })) ?? [];

  const cashFlowData =
    data?.tesoreria_mensual.map((r) => ({
      periodo: r.periodo,
      facturado: r.ingresos_facturados,
      cobrado: r.cobros_reales,
      neto: Number((r.cobros_reales - r.ingresos_facturados).toFixed(2)),
    })) ?? [];

  const margen =
    data?.margen_km_eur != null ? fmtEur(data.margen_km_eur) : p.finanzas.kpiMargenNone;

  return (
    <AppShell active="finanzas">
      <header className="ab-header z-10 flex h-16 shrink-0 items-center justify-between border-b border-zinc-200 bg-white/90 px-8 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-950/85">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">{p.finanzas.title}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">{p.finanzas.subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/finanzas/tesoreria"
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-600 px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50 dark:border-emerald-500 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
          >
            <Landmark className="w-4 h-4" />
            {p.finanzas.linkBank}
          </Link>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700 disabled:opacity-50 dark:text-blue-400 dark:hover:text-blue-300"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            {p.finanzas.refresh}
          </button>
        </div>
      </header>

      <main className="p-8 space-y-8 flex-1 overflow-y-auto">
        {error && (
          <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-950 dark:border-blue-900/40 dark:bg-blue-950/35 dark:text-blue-100">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">{p.finanzas.kpiIngresos}</p>
            <p className="ab-kpi-value text-zinc-900 dark:text-zinc-100">{loading ? "…" : data ? fmtEur(data.ingresos) : "—"}</p>
            <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{p.finanzas.kpiIngresosSub}</p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">{p.finanzas.kpiGastos}</p>
            <p className="ab-kpi-value">{loading ? "…" : data ? fmtEur(data.gastos) : "—"}</p>
            <p className="mt-2 flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400">
              <TrendingDown className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
              {p.finanzas.kpiGastosSub}
            </p>
          </div>
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">{p.finanzas.kpiEbitda}</p>
            <p className="ab-kpi-value text-blue-600 dark:text-blue-400">{loading ? "…" : data ? fmtEur(data.ebitda) : "—"}</p>
            <p className="mt-2 flex items-center gap-1 text-xs text-zinc-500 dark:text-zinc-400">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              {p.finanzas.kpiEbitdaSub}
            </p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">{p.finanzas.kpiMargen}</p>
            <p className="ab-kpi-value flex items-center gap-2">
              <Gauge className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              {loading ? "…" : margen}
            </p>
            <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
              {p.finanzas.kpiMargenSubPrefix}
              {loading ? "…" : data ? `${data.total_km_estimados_snapshot.toFixed(1)} ${p.finanzas.kmUnit}` : "—"}
              {p.finanzas.kpiMargenSubSuffix}
            </p>
          </div>
        </div>

        <div className="ab-card rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-6">
            <div>
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{p.finanzas.chartIgTitle}</h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{p.finanzas.chartIgSub}</p>
            </div>
          </div>
          <div className="h-80 w-full min-w-0">
            {chartData.length === 0 && !loading ? (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{p.finanzas.chartEmpty}</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#71717a" strokeOpacity={0.35} vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fill: "#71717a", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip
                    formatter={(value) => fmtEur(Number(value ?? 0))}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "rgb(63 63 70)",
                      backgroundColor: "rgb(24 24 27)",
                      color: "rgb(244 244 245)",
                    }}
                  />
                  <Legend />
                  <Bar dataKey="ingresos" name={p.finanzas.chartIngresos} fill="#2563eb" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="gastos" name={p.finanzas.chartGastos} fill="#0b1224" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="ab-card rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-6">
            <div>
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{p.finanzas.cfTitle}</h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{p.finanzas.cfSub}</p>
            </div>
          </div>
          <div className="h-80 w-full min-w-0">
            {cashFlowData.length === 0 && !loading ? (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{p.finanzas.cfEmpty}</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cashFlowData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#71717a" strokeOpacity={0.35} vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fill: "#71717a", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#71717a", fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip
                    formatter={(value) => fmtEur(Number(value ?? 0))}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "rgb(63 63 70)",
                      backgroundColor: "rgb(24 24 27)",
                      color: "rgb(244 244 245)",
                    }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="facturado" name={p.finanzas.cfFacturado} stroke="#2563eb" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="cobrado" name={p.finanzas.cfCobrado} stroke="#059669" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="neto" name={p.finanzas.cfNeto} stroke="#0b1224" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </main>
    </AppShell>
  );
}
