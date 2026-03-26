"use client";

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
import { Activity, BarChart3, Gauge, TrendingUp } from "lucide-react";

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

  if (!enabled) {
    return null;
  }

  return (
    <section className="space-y-4" aria-labelledby="dash-economic-advanced">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h2
            id="dash-economic-advanced"
            className="text-lg font-bold text-slate-100 tracking-tight"
          >
            Vista económica avanzada
          </h2>
          <p className="text-sm text-slate-400">
            Math Engine · margen/km, combustible, equilibrio y rentabilidad por cliente (solo owner)
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="text-sm font-semibold text-sky-400 hover:text-sky-300 disabled:opacity-50"
        >
          {loading ? "Cargando…" : "Actualizar"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          {error}
        </div>
      )}

      <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 shadow-xl shadow-black/40">
        {loading && !data ? (
          <div className="animate-pulse grid grid-cols-12 gap-4 min-h-[320px]">
            <div className="col-span-12 h-8 bg-slate-800 rounded w-1/3" />
            <div className="col-span-12 h-64 bg-slate-900 rounded-xl" />
          </div>
        ) : data ? (
          <div className="grid grid-cols-12 gap-4">
            {/* KPI row — 1 col móvil, 2 tablet, 3 desktop (tres métricas) */}
            <div className="col-span-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase tracking-wide">
                <Activity className="w-4 h-4 text-sky-400" />
                Coste medio / km (30d)
              </div>
              <p className="mt-2 text-2xl font-bold text-white tabular-nums">
                {data.coste_medio_km_ultimos_30d != null
                  ? formatEUR4(data.coste_medio_km_ultimos_30d)
                  : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {data.km_operativos_ultimos_30d.toLocaleString("es-ES", { maximumFractionDigits: 1 })} km ·{" "}
                {formatEUR(data.gastos_operativos_ultimos_30d)} gastos
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase tracking-wide">
                <Gauge className="w-4 h-4 text-violet-400" />
                Punto equilibrio (mes)
              </div>
              <p className="mt-2 text-lg font-bold text-white leading-tight">
                {data.punto_equilibrio_mensual.ingreso_equilibrio_estimado_eur != null
                  ? formatEUR(data.punto_equilibrio_mensual.ingreso_equilibrio_estimado_eur)
                  : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {data.punto_equilibrio_mensual.km_equilibrio_estimados != null
                  ? `${data.punto_equilibrio_mensual.km_equilibrio_estimados.toLocaleString("es-ES")} km eq.`
                  : "Km eq. N/D"}{" "}
                · GF {formatEUR(data.punto_equilibrio_mensual.gastos_fijos_mes_eur)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase tracking-wide">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                Contribución
              </div>
              <p className="mt-2 text-2xl font-bold text-white tabular-nums">
                {data.punto_equilibrio_mensual.margen_contribucion_ratio != null
                  ? `${(data.punto_equilibrio_mensual.margen_contribucion_ratio * 100).toFixed(1)} %`
                  : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-1 truncate" title={data.punto_equilibrio_mensual.nota_metodologia}>
                {data.punto_equilibrio_mensual.nota_metodologia.length > 90
                  ? `${data.punto_equilibrio_mensual.nota_metodologia.slice(0, 90)}…`
                  : data.punto_equilibrio_mensual.nota_metodologia}
              </p>
            </div>
            </div>

            {/* Ingresos vs Gastos — áreas */}
            <div className="col-span-12 lg:col-span-7 rounded-xl border border-slate-800 bg-slate-900/50 p-4 min-h-[300px]">
              <div className="flex items-center gap-2 mb-3 text-slate-300 text-sm font-semibold">
                <BarChart3 className="w-4 h-4 text-cyan-400" />
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
            <div className="col-span-12 lg:col-span-5 rounded-xl border border-slate-800 bg-slate-900/50 p-4 min-h-[300px]">
              <div className="flex items-center gap-2 mb-3 text-slate-300 text-sm font-semibold">
                Gastos por categoría
              </div>
              <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <Treemap
                    data={data.gastos_por_categoria}
                    dataKey="value"
                    nameKey="name"
                    stroke="#0f172a"
                    fill="#3b82f6"
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
            <div className="col-span-12 rounded-xl border border-slate-800 bg-slate-900/50 p-4 min-h-[320px]">
              <div className="flex items-center gap-2 mb-3 text-slate-300 text-sm font-semibold">
                Margen neto / km vs coste combustible / km
              </div>
              <p className="text-xs text-slate-500 mb-2">
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
            <div className="col-span-12 rounded-xl border border-slate-800 bg-slate-900/50 p-4 min-w-0">
              <div className="text-slate-300 text-sm font-semibold mb-3">Top 5 rentabilidad (margen % · prorrateo)</div>
              <div className="w-full overflow-x-auto min-w-0">
              <table className="w-full min-w-[800px] text-sm text-left text-slate-300">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase">
                    <th className="py-2 pr-4">Cliente</th>
                    <th className="py-2 pr-4">Ingreso neto</th>
                    <th className="py-2 pr-4">Gasto asignado</th>
                    <th className="py-2">Margen %</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_clientes_rentabilidad.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-6 text-slate-500">
                        Sin datos de facturación por cliente.
                      </td>
                    </tr>
                  ) : (
                    data.top_clientes_rentabilidad.map((r) => (
                      <tr key={r.cliente_id} className="border-b border-slate-800/80">
                        <td className="py-2 pr-4 font-medium text-white">{r.cliente_nombre}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatEUR(r.ingresos_netos_eur)}</td>
                        <td className="py-2 pr-4 tabular-nums">{formatEUR(r.gasto_asignado_eur)}</td>
                        <td className="py-2 tabular-nums text-emerald-400">{r.margen_pct.toFixed(1)} %</td>
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
