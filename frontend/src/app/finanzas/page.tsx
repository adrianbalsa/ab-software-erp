"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Gauge, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function FinanzasPage() {
  const { data, loading, error, refresh } = useFinanceDashboard();

  const chartData =
    data?.ingresos_vs_gastos_mensual.map((r) => ({
      periodo: r.periodo,
      ingresos: r.ingresos,
      gastos: r.gastos,
    })) ?? [];

  const margen =
    data?.margen_km_eur != null
      ? formatEUR(data.margen_km_eur)
      : "— (sin km facturados)";

  return (
    <AppShell active="finanzas">
      <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 z-10 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
            Dashboard financiero
          </h1>
          <p className="text-sm text-slate-500">
            EBITDA, margen por km (snapshot facturado) y comparativa mensual
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] hover:text-[#1d4ed8] disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
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
            {error} — ¿JWT en <code className="text-xs bg-white/60 px-1 rounded">localStorage</code>?
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">Ingresos totales</p>
            <p className="ab-kpi-value text-[#0b1224]">
              {loading ? "…" : data ? formatEUR(data.ingresos) : "—"}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Bases imponibles facturadas (sin IVA)
            </p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">Gastos operativos</p>
            <p className="ab-kpi-value">
              {loading ? "…" : data ? formatEUR(data.gastos) : "—"}
            </p>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <TrendingDown className="w-3.5 h-3.5 text-amber-600" />
              Tickets netos sin IVA
            </p>
          </div>
          <div className="ab-kpi ab-kpi-accent">
            <p className="ab-kpi-label">EBITDA neto</p>
            <p className="ab-kpi-value text-[#2563eb]">
              {loading ? "…" : data ? formatEUR(data.ebitda) : "—"}
            </p>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
              ingresos − gastos
            </p>
          </div>
          <div className="ab-kpi">
            <p className="ab-kpi-label">Margen / km</p>
            <p className="ab-kpi-value flex items-center gap-2">
              <Gauge className="w-6 h-6 text-[#2563eb]" />
              {loading ? "…" : margen}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              EBITDA ÷ total_km_estimados_snapshot (
              {loading ? "…" : data ? `${data.total_km_estimados_snapshot.toFixed(1)} km` : "—"})
            </p>
          </div>
        </div>

        <div className="ab-card rounded-2xl p-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 mb-6">
            <div>
              <h2 className="text-lg font-bold text-[#0b1224]">
                Ingresos vs gastos (últimos 6 meses)
              </h2>
              <p className="text-sm text-slate-500">
                Ingresos por <code className="text-xs">fecha_emision</code> de facturas;
                gastos por <code className="text-xs">fecha</code> de tickets
              </p>
            </div>
          </div>
          <div className="h-80 w-full min-w-0">
            {chartData.length === 0 && !loading ? (
              <p className="text-sm text-slate-500">Sin datos para graficar.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fill: "#64748b", fontSize: 11 }} />
                  <YAxis
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    formatter={(value) => formatEUR(Number(value ?? 0))}
                    contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }}
                  />
                  <Legend />
                  <Bar
                    dataKey="ingresos"
                    name="Ingresos"
                    fill="#2563eb"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="gastos"
                    name="Gastos"
                    fill="#0b1224"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </main>
    </AppShell>
  );
}
