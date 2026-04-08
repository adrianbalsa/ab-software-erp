"use client";

import { useEffect } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { useEconomicOverview } from "@/hooks/useEconomicOverview";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="dashboard-bento space-y-4 rounded-2xl p-6">
          <div className="h-4 w-1/3 rounded bg-zinc-800" />
          <div className="h-[280px] rounded-xl bg-zinc-800/60" />
        </div>
        <div className="dashboard-bento space-y-4 rounded-2xl p-6">
          <div className="h-4 w-2/5 rounded bg-zinc-800" />
          <div className="h-[280px] rounded-xl bg-zinc-800/60" />
        </div>
      </div>
      <div className="dashboard-bento space-y-4 rounded-2xl p-6">
        <div className="h-4 w-1/2 rounded bg-zinc-800" />
        <div className="h-[280px] rounded-xl bg-zinc-800/60" />
      </div>
    </div>
  );
}

export function EconomicOverview() {
  const { data, loading, error, refresh, hasAreaData } = useEconomicOverview();

  useEffect(() => {
    if (!error) return;
    toast.error(`Visión económica: ${error}`, { id: "economic-overview-error" });
  }, [error]);

  if (loading) {
    return (
      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-zinc-100">Visión económica (Math Engine)</h2>
            <p className="text-sm text-zinc-500">Costes por categoría, margen por cliente e ingresos vs gastos</p>
          </div>
        </div>
        <OverviewSkeleton />
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-zinc-100">Visión económica (Math Engine)</h2>
            <p className="text-sm text-zinc-500">Requiere sesión y datos de finanzas, gastos y facturas</p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="text-sm font-semibold text-emerald-400 hover:text-emerald-300"
          >
            Reintentar
          </button>
        </div>
        <div className="dashboard-bento rounded-2xl px-4 py-3 text-sm text-zinc-500">
          No se pudieron cargar los gráficos. El detalle se muestra en el aviso.
        </div>
      </section>
    );
  }

  const donutData = data.costDistribution;
  const barData = data.topClientesMargen;
  const areaRows = data.ingresosVsGastos.map((r) => ({
    periodo: r.periodo,
    ingresos: r.ingresos,
    gastos: r.gastos,
  }));

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-100">Visión económica (Math Engine)</h2>
          <p className="text-sm text-zinc-500">
            EBITDA {formatEUR(data.dashboard.ebitda)} · margen estimado por cliente proporcional al ingreso
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="text-sm font-semibold text-emerald-400 hover:text-emerald-300"
        >
          Actualizar gráficos
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="dashboard-bento rounded-2xl p-6">
          <h3 className="mb-1 text-sm font-semibold text-zinc-100">Distribución de costes</h3>
          <p className="mb-4 text-xs text-zinc-500">Gastos operativos por categoría (neto sin IVA)</p>
          <div className="h-[min(260px,40vh)] min-h-[220px] w-full min-w-0 sm:h-[280px] sm:min-h-[240px]">
            {donutData.length === 0 ? (
              <p className="py-12 text-center text-sm text-zinc-500">Sin gastos clasificados para mostrar.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={68}
                    outerRadius={96}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                    strokeWidth={0}
                  >
                    {donutData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => formatEUR(Number(value ?? 0))}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#3f3f46",
                      background: "#18181b",
                      fontSize: 12,
                      color: "#e4e4e7",
                    }}
                  />
                  <Legend
                    layout="horizontal"
                    verticalAlign="bottom"
                    align="center"
                    wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="dashboard-bento rounded-2xl p-6">
          <h3 className="mb-1 text-sm font-semibold text-zinc-100">Top 5 clientes por margen</h3>
          <p className="mb-4 text-xs text-zinc-500">Margen estimado = ingreso × (EBITDA ÷ ingresos)</p>
          <div className="h-[min(260px,40vh)] min-h-[220px] w-full min-w-0 sm:h-[280px] sm:min-h-[240px]">
            {barData.length === 0 ? (
              <p className="py-12 text-center text-sm text-zinc-500">Sin facturas con cliente para rankear.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={barData}
                  layout="vertical"
                  margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                  />
                  <YAxis
                    type="category"
                    dataKey="cliente"
                    width={120}
                    tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value) => formatEUR(Number(value ?? 0))}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#3f3f46",
                      background: "#18181b",
                      fontSize: 12,
                      color: "#e4e4e7",
                    }}
                  />
                  <Bar
                    dataKey="margen"
                    name="Margen est."
                    radius={[0, 6, 6, 0]}
                    fill="#059669"
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="dashboard-bento rounded-2xl p-6">
        <h3 className="mb-1 text-sm font-semibold text-zinc-100">Histórico ingresos vs gastos</h3>
        <p className="mb-4 text-xs text-zinc-500">Últimos 6 meses (ingresos por facturas; gastos por tickets)</p>
        <div className="h-[min(280px,42vh)] min-h-[220px] w-full min-w-0 sm:h-[300px] sm:min-h-[260px]">
          {!hasAreaData ? (
            <p className="py-12 text-center text-sm text-zinc-500">Sin movimientos en la ventana de 6 meses.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={areaRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradIngresos" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1d4ed8" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#1d4ed8" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradGastos" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#475569" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#475569" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                <XAxis dataKey="periodo" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                <YAxis
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  formatter={(value) => formatEUR(Number(value ?? 0))}
                  labelFormatter={(l) => String(l)}
                  contentStyle={{
                    borderRadius: 12,
                    borderColor: "#3f3f46",
                    background: "#18181b",
                    fontSize: 12,
                    color: "#e4e4e7",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }} />
                <Area
                  type="monotone"
                  dataKey="ingresos"
                  name="Ingresos"
                  stroke="#2563eb"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#gradIngresos)"
                />
                <Area
                  type="monotone"
                  dataKey="gastos"
                  name="Gastos"
                  stroke="#334155"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#gradGastos)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </section>
  );
}
