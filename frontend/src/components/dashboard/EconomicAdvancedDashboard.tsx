"use client";

import { useEffect } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, BarChart3, Gauge, Info, TrendingUp, Zap } from "lucide-react";
import { toast } from "sonner";

import { useEconomicInsights } from "@/hooks/useEconomicInsights";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

function formatEUR4(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 4 });
}

type Props = {
  enabled: boolean;
};

export function EconomicAdvancedDashboard({ enabled }: Props) {
  const { data, loading, error, refresh } = useEconomicInsights({ enabled });

  useEffect(() => {
    if (!enabled || !error) return;
    toast.error(error, { id: "economic-advanced-error" });
  }, [enabled, error]);

  if (!enabled) {
    return null;
  }

  return (
    <section className="space-y-4" aria-labelledby="dash-economic-advanced">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h2
            id="dash-economic-advanced"
            className="text-lg font-bold tracking-tight text-zinc-100"
          >
            Vista económica avanzada
          </h2>
          <p className="text-sm text-zinc-400">
            Math Engine · margen/km, combustible, equilibrio y rentabilidad por cliente (solo owner)
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="text-sm font-semibold text-emerald-500 hover:text-emerald-400 disabled:opacity-50"
        >
          {loading ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      <div className="dashboard-bento rounded-2xl p-6 shadow-xl shadow-black/40">
        {loading && !data ? (
          <div className="animate-pulse grid grid-cols-12 gap-4 min-h-[320px]">
            <div className="col-span-12 h-8 w-1/3 rounded bg-zinc-800" />
            <div className="col-span-12 h-64 rounded-xl bg-zinc-900" />
          </div>
        ) : data ? (
          <div className="grid grid-cols-12 gap-4">
            {/* Real-cost linker — KPIs agregados (advanced-metrics) */}
            <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-emerald-500/25 bg-gradient-to-br from-emerald-950/40 to-zinc-900/50 p-4 backdrop-blur-md">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-200/90">
                    <TrendingUp className="h-4 w-4 text-emerald-400" />
                    Índice de Margen Real
                  </div>
                  <span
                    className="shrink-0 text-zinc-500"
                    title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
                  >
                    <Info className="h-4 w-4" aria-hidden />
                  </span>
                </div>
                <p className="mt-2 text-2xl font-bold tabular-nums text-white">
                  {data.real_margin_index != null && !Number.isNaN(data.real_margin_index)
                    ? `${data.real_margin_index >= 0 ? "+" : ""}${data.real_margin_index.toFixed(1)} %`
                    : "—"}
                </p>
                <p className="mt-1 text-xs leading-snug text-zinc-500">
                  Desviación del margen P&L agregado (real vs estimación km×coste). Positivo: el real supera el
                  proxy.
                </p>
              </div>
              <div className="rounded-xl border border-amber-500/25 bg-gradient-to-br from-amber-950/30 to-zinc-900/50 p-4 backdrop-blur-md">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-200/90">
                    <Zap className="h-4 w-4 text-amber-400" />
                    Ratio de Eficiencia de Combustible
                  </div>
                  <span
                    className="shrink-0 text-zinc-500"
                    title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
                  >
                    <Info className="h-4 w-4" aria-hidden />
                  </span>
                </div>
                <p className="mt-2 text-2xl font-bold tabular-nums text-white">
                  {data.fuel_efficiency_ratio != null && !Number.isNaN(data.fuel_efficiency_ratio)
                    ? `${data.fuel_efficiency_ratio.toFixed(2)} € / €`
                    : "—"}
                </p>
                <p className="mt-1 text-xs leading-snug text-zinc-500">
                  Ingresos por porte completados frente a cada euro de combustible imputado desde tickets.
                </p>
              </div>
            </div>

            {/* KPI row — 1 col móvil, 2 tablet, 3 desktop (tres métricas) */}
            <div className="col-span-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-md transition-shadow hover:shadow-[0_0_20px_rgba(16,185,129,0.1)]">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                <Activity className="h-4 w-4 text-emerald-500" />
                Coste medio / km (30d)
              </div>
              <p className="mt-2 text-2xl font-bold text-white tabular-nums">
                {data.coste_medio_km_ultimos_30d != null
                  ? formatEUR4(data.coste_medio_km_ultimos_30d)
                  : "—"}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {data.km_operativos_ultimos_30d.toLocaleString("es-ES", { maximumFractionDigits: 1 })} km ·{" "}
                {formatEUR(data.gastos_operativos_ultimos_30d)} gastos
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-md transition-shadow hover:shadow-[0_0_20px_rgba(16,185,129,0.1)]">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                <Gauge className="h-4 w-4 text-amber-400" />
                Punto equilibrio (mes)
              </div>
              <p className="mt-2 text-lg font-bold text-white leading-tight">
                {data.punto_equilibrio_mensual.ingreso_equilibrio_estimado_eur != null
                  ? formatEUR(data.punto_equilibrio_mensual.ingreso_equilibrio_estimado_eur)
                  : "—"}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {data.punto_equilibrio_mensual.km_equilibrio_estimados != null
                  ? `${data.punto_equilibrio_mensual.km_equilibrio_estimados.toLocaleString("es-ES")} km eq.`
                  : "Km eq. N/D"}{" "}
                · GF {formatEUR(data.punto_equilibrio_mensual.gastos_fijos_mes_eur)}
              </p>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-md transition-shadow hover:shadow-[0_0_20px_rgba(16,185,129,0.1)]">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                <TrendingUp className="h-4 w-4 text-emerald-500" />
                Contribución
              </div>
              <p className="mt-2 text-2xl font-bold text-white tabular-nums">
                {data.punto_equilibrio_mensual.margen_contribucion_ratio != null
                  ? `${(data.punto_equilibrio_mensual.margen_contribucion_ratio * 100).toFixed(1)} %`
                  : "—"}
              </p>
              <p className="mt-1 truncate text-xs text-zinc-500" title={data.punto_equilibrio_mensual.nota_metodologia}>
                {data.punto_equilibrio_mensual.nota_metodologia.length > 90
                  ? `${data.punto_equilibrio_mensual.nota_metodologia.slice(0, 90)}…`
                  : data.punto_equilibrio_mensual.nota_metodologia}
              </p>
            </div>
            </div>

            {/* Ingresos vs Gastos — áreas */}
            <div className="col-span-12 min-h-[300px] rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 lg:col-span-7">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
                <BarChart3 className="h-4 w-4 text-emerald-500" />
                Ingresos vs gastos (12 meses)
              </div>
              <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.ingresos_vs_gastos_mensual} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="ingG" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22c55e" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gasG" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f97316" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#f97316" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="periodo" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                      labelStyle={{ color: "#e2e8f0" }}
                      formatter={(v) => formatEUR(Number(v ?? 0))}
                    />
                    <Legend wrapperStyle={{ color: "#cbd5e1" }} />
                    <Area
                      type="monotone"
                      dataKey="ingresos"
                      name="Ingresos"
                      stroke="#22c55e"
                      fill="url(#ingG)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="gastos"
                      name="Gastos"
                      stroke="#f97316"
                      fill="url(#gasG)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Treemap categorías */}
            <div className="col-span-12 min-h-[300px] rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 lg:col-span-5">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
                Gastos por categoría
              </div>
              <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <Treemap
                    data={data.gastos_por_categoria}
                    dataKey="value"
                    nameKey="name"
                    stroke="#0f172a"
                    fill="#10b981"
                  >
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                      formatter={(v) => formatEUR(Number(v ?? 0))}
                    />
                  </Treemap>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Margen/km vs gasoil/km */}
            <div className="col-span-12 min-h-[320px] rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-300">
                Margen neto / km vs coste combustible / km
              </div>
              <p className="mb-2 text-xs text-zinc-500">
                Responde: cuánto queda por km tras gastos operativos del mes frente al coste de gasoil imputado por km
                facturado.
              </p>
              <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.margen_km_vs_gasoil_mensual} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="periodo" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis
                      yAxisId="left"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickFormatter={(v) => `${v.toFixed(2)}`}
                      label={{ value: "€/km margen", angle: -90, position: "insideLeft", fill: "#64748b" }}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickFormatter={(v) => `${v.toFixed(2)}`}
                      label={{ value: "€/km gasoil", angle: 90, position: "insideRight", fill: "#64748b" }}
                    />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
                      formatter={(v) =>
                        v == null || v === "" ? "—" : formatEUR4(Number(v))
                      }
                    />
                    <Legend wrapperStyle={{ color: "#cbd5e1" }} />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="margen_neto_km_eur"
                      name="Margen / km"
                      stroke="#34d399"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="coste_combustible_por_km_eur"
                      name="Gasoil / km"
                      stroke="#fb923c"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top clientes */}
            <div className="col-span-12 min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
              <div className="mb-3 text-sm font-semibold text-zinc-300">Top 5 rentabilidad (margen % · prorrateo)</div>
              <div className="min-w-0 w-full overflow-x-auto">
              <table className="w-full min-w-[800px] text-left text-sm text-zinc-300">
                <thead>
                  <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-500">
                    <th className="py-2 pr-4">Cliente</th>
                    <th className="py-2 pr-4">Ingreso neto</th>
                    <th className="py-2 pr-4">Gasto asignado</th>
                    <th className="py-2">Margen %</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_clientes_rentabilidad.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-6 text-zinc-500">
                        Sin datos de facturación por cliente.
                      </td>
                    </tr>
                  ) : (
                    data.top_clientes_rentabilidad.map((r) => (
                      <tr key={r.cliente_id} className="border-b border-zinc-900 transition-colors hover:bg-zinc-800/30">
                        <td className="py-2 pr-4 font-medium text-white">{r.cliente_nombre}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatEUR(r.ingresos_netos_eur)}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatEUR(r.gasto_asignado_eur)}</td>
                        <td className="py-2 tabular-nums text-emerald-500">{r.margen_pct.toFixed(1)} %</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
