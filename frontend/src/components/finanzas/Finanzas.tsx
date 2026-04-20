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
      <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 z-10 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">{p.finanzas.title}</h1>
          <p className="text-sm text-slate-500">{p.finanzas.subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/finanzas/tesoreria"
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-600 px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50"
          >
            <Landmark className="w-4 h-4" />
            {p.finanzas.linkBank}
          </Link>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] hover:text-[#1d4ed8] disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            {p.finanzas.refresh}
          </button>
        </div>
      </header>

      <main className="p-8 space-y-8 flex-1 overflow-y-auto">
        {error && (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{
              background: "rgba(37, 99, 235, 0.06)",
              borderColor: "rgba(37, 99, 235, 0.2)",
              color: "#0b1224",
            }}
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">{p.finanzas.kpiIngresos}</p>
            <p className="ab-kpi-value text-[#0b1224]">{loading ? "…" : data ? fmtEur(data.ingresos) : "—"}</p>
            <p className="text-xs text-slate-500 mt-2">{p.finanzas.kpiIngresosSub}</p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">{p.finanzas.kpiGastos}</p>
            <p className="ab-kpi-value">{loading ? "…" : data ? fmtEur(data.gastos) : "—"}</p>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <TrendingDown className="w-3.5 h-3.5 text-amber-600" />
              {p.finanzas.kpiGastosSub}
            </p>
          </div>
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">{p.finanzas.kpiEbitda}</p>
            <p className="ab-kpi-value text-[#2563eb]">{loading ? "…" : data ? fmtEur(data.ebitda) : "—"}</p>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
              {p.finanzas.kpiEbitdaSub}
            </p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">{p.finanzas.kpiMargen}</p>
            <p className="ab-kpi-value flex items-center gap-2">
              <Gauge className="w-6 h-6 text-[#2563eb]" />
              {loading ? "…" : margen}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              {p.finanzas.kpiMargenSubPrefix}
              {loading ? "…" : data ? `${data.total_km_estimados_snapshot.toFixed(1)} ${p.finanzas.kmUnit}` : "—"}
              {p.finanzas.kpiMargenSubSuffix}
            </p>
          </div>
        </div>

        <div className="ab-card rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-6">
            <div>
              <h2 className="text-lg font-bold text-[#0b1224]">{p.finanzas.chartIgTitle}</h2>
              <p className="text-sm text-slate-500">{p.finanzas.chartIgSub}</p>
            </div>
          </div>
          <div className="h-80 w-full min-w-0">
            {chartData.length === 0 && !loading ? (
              <p className="text-sm text-slate-500">{p.finanzas.chartEmpty}</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fill: "#64748b", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(value) => fmtEur(Number(value ?? 0))} contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }} />
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
              <h2 className="text-lg font-bold text-[#0b1224]">{p.finanzas.cfTitle}</h2>
              <p className="text-sm text-slate-500">{p.finanzas.cfSub}</p>
            </div>
          </div>
          <div className="h-80 w-full min-w-0">
            {cashFlowData.length === 0 && !loading ? (
              <p className="text-sm text-slate-500">{p.finanzas.cfEmpty}</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cashFlowData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fill: "#64748b", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(value) => fmtEur(Number(value ?? 0))} contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }} />
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
