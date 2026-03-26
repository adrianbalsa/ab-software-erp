"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getAdvancedMetrics,
  getAlertasMantenimiento,
  isAlertaKm,
  type AdvancedMetricsMonthRow,
} from "@/lib/api";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function formatPeriodLabel(yyyyMm: string) {
  const [y, m] = yyyyMm.split("-").map(Number);
  if (!y || !m) return yyyyMm;
  return new Date(y, m - 1, 1).toLocaleDateString("es-ES", {
    month: "short",
    year: "2-digit",
  });
}

type ChartRow = {
  periodo: string;
  label: string;
  ingresos: number;
  gastos: number;
  costeKm: number | null;
  co2: number;
};

function toRows(meses: AdvancedMetricsMonthRow[]): ChartRow[] {
  return meses.map((r) => ({
    periodo: r.periodo,
    label: formatPeriodLabel(r.periodo),
    ingresos: r.ingresos_facturacion_eur,
    gastos: r.gastos_operativos_eur,
    costeKm: r.coste_por_km_eur,
    co2: r.emisiones_co2_kg,
  }));
}

function FleetAdminAlertsStrip() {
  const [criticos, setCriticos] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await getAlertasMantenimiento();
        const n = rows.filter(
          (r) => !isAlertaKm(r) && r.urgencia === "CRITICO",
        ).length;
        if (!cancelled) setCriticos(n);
      } catch {
        if (!cancelled) setCriticos(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (criticos === null || criticos === 0) return null;

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
      <CalendarDays className="h-4 w-4 shrink-0 text-amber-800" aria-hidden />
      <span>
        <strong>{criticos}</strong> alerta(s) administrativa(s) crítica(s) (ITV / seguro / tacógrafo).
      </span>
      <Link
        href="/flota/mantenimiento"
        className="font-semibold text-[#2563eb] underline-offset-2 hover:underline"
      >
        Ver en Taller — mantenimiento
      </Link>
    </div>
  );
}

export function AdvancedCharts() {
  const [rows, setRows] = useState<ChartRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nota, setNota] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdvancedMetrics();
      setRows(toRows(res.meses));
      setNota(res.nota_metodologia ?? null);
    } catch (e: unknown) {
      setRows([]);
      setError(e instanceof Error ? e.message : "Error al cargar métricas avanzadas");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasData = rows.some(
    (r) => r.ingresos > 0 || r.gastos > 0 || (r.costeKm != null && r.costeKm > 0) || r.co2 > 0,
  );

  const chartWrap = "w-full min-w-0 min-h-[240px] sm:min-h-[280px] h-[min(42vh,320px)]";

  if (loading) {
    return (
      <section className="space-y-4" aria-busy="true">
        <div className="h-4 bg-zinc-200/90 rounded w-1/3 max-w-xs animate-pulse" />
        <div className="grid gap-6 lg:grid-cols-1 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="ab-card rounded-2xl p-6 animate-pulse">
              <div className="h-3 bg-zinc-200 rounded w-2/5 mb-4" />
              <div className={`${chartWrap} bg-zinc-100 rounded-xl`} />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-950">
        <p className="font-semibold">Métricas avanzadas no disponibles</p>
        <p className="mt-1 text-amber-900/90">{error}</p>
        <p className="mt-2 text-xs text-amber-800/80">
          Requiere rol <code className="rounded bg-white/80 px-1">ADMIN</code> o{" "}
          <code className="rounded bg-white/80 px-1">GESTOR</code> en el JWT (app_metadata.role).
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-labelledby="advanced-charts-heading">
      <div>
        <h2
          id="advanced-charts-heading"
          className="text-lg font-bold text-[#0b1224] tracking-tight"
        >
          Dashboard económico avanzado
        </h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Facturación (Math Engine), gastos operativos, coste por km y huella CO₂ (últimos 6 meses).
        </p>
        {nota ? <p className="text-xs text-slate-400 mt-1 max-w-3xl">{nota}</p> : null}
      </div>

      {!loading && !error ? <FleetAdminAlertsStrip /> : null}

      {!hasData ? (
        <p className="text-sm text-slate-500 ab-card rounded-2xl p-6">
          Sin datos suficientes en el periodo para graficar (facturas, gastos o portes).
        </p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-1 xl:grid-cols-3">
          <div className="ab-card rounded-2xl p-4 sm:p-6 overflow-hidden">
            <h3 className="text-sm font-bold text-zinc-800 mb-1">Margen de contribución</h3>
            <p className="text-xs text-zinc-500 mb-3">Ingresos (verde) vs gastos operativos (rojo)</p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} className="text-zinc-500" />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                  <Tooltip
                    formatter={(v: number | string) => formatEUR(Number(v))}
                    labelFormatter={(_, p) => (p?.[0]?.payload?.periodo as string) ?? ""}
                  />
                  <Legend />
                  <Bar dataKey="ingresos" name="Ingresos" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="gastos" name="Gastos" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="ab-card rounded-2xl p-4 sm:p-6 overflow-hidden">
            <h3 className="text-sm font-bold text-zinc-800 mb-1">Coste real por km</h3>
            <p className="text-xs text-zinc-500 mb-3">
              (Combustible + peajes + mantenimiento) / km en portes
            </p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${Number(v).toFixed(2)} €`}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    formatter={(v: number | string) =>
                      v == null || v === ""
                        ? "—"
                        : `${Number(v).toFixed(2)} €/km`
                    }
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="costeKm"
                    name="€/km"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="ab-card rounded-2xl p-4 sm:p-6 overflow-hidden xl:col-span-1">
            <h3 className="text-sm font-bold text-zinc-800 mb-1">EBITDA verde</h3>
            <p className="text-xs text-zinc-500 mb-3">Ingresos (columnas) y emisiones CO₂ (línea)</p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis
                    yAxisId="eur"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${Math.round(v / 1000)}k`}
                  />
                  <YAxis
                    yAxisId="co2"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    formatter={(v: number | string, name: string) => {
                      if (name === "Ingresos") return formatEUR(Number(v));
                      return `${Number(v).toFixed(1)} kg`;
                    }}
                  />
                  <Legend />
                  <Bar
                    yAxisId="eur"
                    dataKey="ingresos"
                    name="Ingresos"
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={48}
                  />
                  <Line
                    yAxisId="co2"
                    type="monotone"
                    dataKey="co2"
                    name="CO₂ (kg)"
                    stroke="#0e7490"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
