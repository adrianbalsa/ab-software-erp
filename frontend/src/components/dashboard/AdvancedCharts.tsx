"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { toast } from "sonner";
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

/** Coerción segura para valores de Recharts (Tooltip / ejes), que pueden ser undefined o arrays. */
function toFiniteNumber(value: unknown, fallback = 0): number {
  if (value == null || value === "") return fallback;
  if (typeof value === "number") return Number.isFinite(value) ? value : fallback;
  if (typeof value === "string") {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }
  if (Array.isArray(value)) {
    const n = Number(value[0]);
    return Number.isFinite(n) ? n : fallback;
  }
  return fallback;
}

function formatTooltipEUR(value: unknown): string {
  const n = toFiniteNumber(value, 0);
  return formatEUR(Number.isFinite(n) ? n : 0);
}

function formatTooltipEurPerKm(value: unknown): string {
  if (value == null || value === "") return "—";
  const n = toFiniteNumber(value, NaN);
  if (Number.isNaN(n)) return "—";
  return `${n.toFixed(2)} €/km`;
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
    <div className="dashboard-bento mb-4 flex flex-wrap items-center gap-2 px-4 py-3 text-sm text-zinc-300">
      <CalendarDays className="h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
      <span>
        <strong className="text-zinc-100">{criticos}</strong> alerta(s) administrativa(s) crítica(s) (ITV / seguro / tacógrafo).
      </span>
      <Link
        href="/flota/mantenimiento"
        className="font-semibold text-emerald-400 underline-offset-2 hover:text-emerald-300 hover:underline"
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

  useEffect(() => {
    if (!error) return;
    toast.error(error, { id: "advanced-metrics-error" });
  }, [error]);

  const hasData = rows.some(
    (r) => r.ingresos > 0 || r.gastos > 0 || (r.costeKm != null && r.costeKm > 0) || r.co2 > 0,
  );

  const chartWrap = "w-full min-w-0 min-h-[240px] sm:min-h-[280px] h-[min(42vh,320px)]";

  if (loading) {
    return (
      <section className="space-y-4" aria-busy="true">
        <div className="h-4 max-w-xs w-1/3 animate-pulse rounded bg-zinc-800" />
        <div className="grid gap-6 lg:grid-cols-1 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="dashboard-bento animate-pulse rounded-2xl p-6">
              <div className="mb-4 h-3 w-2/5 rounded bg-zinc-800" />
              <div className={`${chartWrap} rounded-xl bg-zinc-800/60`} />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="dashboard-bento rounded-2xl px-4 py-4 text-sm text-zinc-500">
        <p className="font-medium text-zinc-300">Métricas avanzadas no disponibles</p>
        <p className="mt-2 text-xs text-zinc-600">
          Requiere rol <code className="rounded bg-zinc-900 px-1 text-zinc-400">ADMIN</code> o{" "}
          <code className="rounded bg-zinc-900 px-1 text-zinc-400">GESTOR</code> en el JWT (app_metadata.role). El detalle
          del error aparece en el aviso.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-labelledby="advanced-charts-heading">
      <div>
        <h2
          id="advanced-charts-heading"
          className="text-lg font-semibold tracking-tight text-zinc-100"
        >
          Dashboard económico avanzado
        </h2>
        <p className="mt-0.5 text-sm text-zinc-500">
          Facturación (Math Engine), gastos operativos, coste por km y huella CO₂ (últimos 6 meses).
        </p>
        {nota ? <p className="mt-1 max-w-3xl text-xs text-zinc-600">{nota}</p> : null}
      </div>

      {!loading && !error ? <FleetAdminAlertsStrip /> : null}

      {!hasData ? (
        <p className="dashboard-bento rounded-2xl p-6 text-sm text-zinc-500">
          Sin datos suficientes en el periodo para graficar (facturas, gastos o portes).
        </p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-1 xl:grid-cols-3">
          <div className="dashboard-bento overflow-hidden rounded-2xl p-4 sm:p-6">
            <h3 className="mb-1 text-sm font-semibold text-zinc-100">Margen de contribución</h3>
            <p className="mb-3 text-xs text-zinc-500">Ingresos (verde) vs gastos operativos (rojo)</p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                  <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                  <YAxis
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    tickFormatter={(v) => `${Math.round(toFiniteNumber(v, 0) / 1000)}k`}
                  />
                  <Tooltip
                    formatter={(value: number | string | ReadonlyArray<number | string> | undefined) =>
                      formatTooltipEUR(value)
                    }
                    labelFormatter={(_, p) => {
                      const first = Array.isArray(p) ? p[0] : undefined;
                      const row = first && typeof first === "object" && "payload" in first
                        ? (first as { payload?: ChartRow }).payload
                        : undefined;
                      return row?.periodo ?? "";
                    }}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#3f3f46",
                      background: "#18181b",
                      fontSize: 12,
                      color: "#e4e4e7",
                    }}
                  />
                  <Legend />
                  <Bar dataKey="ingresos" name="Ingresos" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="gastos" name="Gastos" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="dashboard-bento overflow-hidden rounded-2xl p-4 sm:p-6">
            <h3 className="mb-1 text-sm font-semibold text-zinc-100">Coste real por km</h3>
            <p className="mb-3 text-xs text-zinc-500">(Combustible + peajes + mantenimiento) / km en portes</p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                  <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                  <YAxis
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    tickFormatter={(v) => `${toFiniteNumber(v, 0).toFixed(2)} €`}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    formatter={(value: number | string | ReadonlyArray<number | string> | undefined) =>
                      formatTooltipEurPerKm(value)
                    }
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#3f3f46",
                      background: "#18181b",
                      fontSize: 12,
                      color: "#e4e4e7",
                    }}
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

          <div className="dashboard-bento overflow-hidden rounded-2xl p-4 sm:p-6 xl:col-span-1">
            <h3 className="mb-1 text-sm font-semibold text-zinc-100">EBITDA verde</h3>
            <p className="mb-3 text-xs text-zinc-500">Ingresos (columnas) y emisiones CO₂ (línea)</p>
            <div className={chartWrap}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                  <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                  <YAxis
                    yAxisId="eur"
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    tickFormatter={(v) => `${Math.round(toFiniteNumber(v, 0) / 1000)}k`}
                  />
                  <YAxis
                    yAxisId="co2"
                    orientation="right"
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    tickFormatter={(v) => String(toFiniteNumber(v, 0))}
                  />
                  <Tooltip
                    formatter={(
                      value: number | string | ReadonlyArray<number | string> | undefined,
                      name,
                    ) => {
                      const n = toFiniteNumber(value, 0);
                      const label = String(name ?? "");
                      if (label === "Ingresos") return formatEUR(n);
                      return `${n.toFixed(1)} kg`;
                    }}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#3f3f46",
                      background: "#18181b",
                      fontSize: 12,
                      color: "#e4e4e7",
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
