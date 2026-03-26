"use client";

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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="ab-card rounded-2xl p-6 space-y-4">
          <div className="h-4 bg-slate-200/90 rounded w-1/3" />
          <div className="h-[280px] bg-slate-200/70 rounded-xl" />
        </div>
        <div className="ab-card rounded-2xl p-6 space-y-4">
          <div className="h-4 bg-slate-200/90 rounded w-2/5" />
          <div className="h-[280px] bg-slate-200/70 rounded-xl" />
        </div>
      </div>
      <div className="ab-card rounded-2xl p-6 space-y-4">
        <div className="h-4 bg-slate-200/90 rounded w-1/2" />
        <div className="h-[280px] bg-slate-200/70 rounded-xl" />
      </div>
    </div>
  );
}

export function EconomicOverview() {
  const { data, loading, error, refresh, hasAreaData } = useEconomicOverview();

  if (loading) {
    return (
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-[#0b1224] tracking-tight">
              Visión económica (Math Engine)
            </h2>
            <p className="text-sm text-slate-500">
              Costes por categoría, margen por cliente e ingresos vs gastos
            </p>
          </div>
        </div>
        <OverviewSkeleton />
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-[#0b1224] tracking-tight">
              Visión económica (Math Engine)
            </h2>
            <p className="text-sm text-slate-500">
              Requiere sesión y datos de finanzas, gastos y facturas
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            className="text-sm font-semibold text-[#2563eb] hover:text-[#1d4ed8]"
          >
            Reintentar
          </button>
        </div>
        <div className="ab-card rounded-2xl px-4 py-3 text-sm text-amber-900 bg-amber-50 border border-amber-200/80">
          {error ?? "Sin datos"}
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
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-[#0b1224] tracking-tight">
            Visión económica (Math Engine)
          </h2>
          <p className="text-sm text-slate-500">
            EBITDA {formatEUR(data.dashboard.ebitda)} · margen estimado por cliente
            proporcional al ingreso
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          className="text-sm font-semibold text-[#2563eb] hover:text-[#1d4ed8]"
        >
          Actualizar gráficos
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="ab-card rounded-2xl p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1">
            Distribución de costes
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Gastos operativos por categoría (neto sin IVA)
          </p>
          <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
            {donutData.length === 0 ? (
              <p className="text-sm text-slate-500 py-12 text-center">
                Sin gastos clasificados para mostrar.
              </p>
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
                      borderColor: "#e2e8f0",
                      fontSize: 12,
                    }}
                  />
                  <Legend
                    layout="horizontal"
                    verticalAlign="bottom"
                    align="center"
                    wrapperStyle={{ fontSize: 11, color: "#475569" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="ab-card rounded-2xl p-6">
          <h3 className="text-sm font-bold text-slate-800 mb-1">
            Top 5 clientes por margen
          </h3>
          <p className="text-xs text-slate-500 mb-4">
            Margen estimado = ingreso × (EBITDA ÷ ingresos)
          </p>
          <div className="h-[min(260px,40vh)] min-h-[220px] sm:h-[280px] sm:min-h-[240px] w-full min-w-0">
            {barData.length === 0 ? (
              <p className="text-sm text-slate-500 py-12 text-center">
                Sin facturas con cliente para rankear.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={barData}
                  layout="vertical"
                  margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                  />
                  <YAxis
                    type="category"
                    dataKey="cliente"
                    width={120}
                    tick={{ fill: "#475569", fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value) => formatEUR(Number(value ?? 0))}
                    contentStyle={{
                      borderRadius: 12,
                      borderColor: "#e2e8f0",
                      fontSize: 12,
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

      <div className="ab-card rounded-2xl p-6">
        <h3 className="text-sm font-bold text-slate-800 mb-1">
          Histórico ingresos vs gastos
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Últimos 6 meses (ingresos por facturas; gastos por tickets)
        </p>
        <div className="h-[min(280px,42vh)] min-h-[220px] sm:h-[300px] sm:min-h-[260px] w-full min-w-0">
          {!hasAreaData ? (
            <p className="text-sm text-slate-500 py-12 text-center">
              Sin movimientos en la ventana de 6 meses.
            </p>
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
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="periodo"
                  tick={{ fill: "#64748b", fontSize: 11 }}
                />
                <YAxis
                  tick={{ fill: "#64748b", fontSize: 11 }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  formatter={(value) => formatEUR(Number(value ?? 0))}
                  labelFormatter={(l) => String(l)}
                  contentStyle={{
                    borderRadius: 12,
                    borderColor: "#e2e8f0",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
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
