"use client";

import React, { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { FinanceTesoreriaMensual } from "@/hooks/useFinanceDashboard";

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
    year: "numeric",
  });
}

export type CashFlowChartProps = {
  data: FinanceTesoreriaMensual[];
  loading?: boolean;
};

export function CashFlowChart({ data, loading }: CashFlowChartProps) {
  const uid = useId().replace(/:/g, "");
  const chartData = data.map((r) => ({
    periodo: r.periodo,
    label: formatPeriodLabel(r.periodo),
    ingresos_facturados: r.ingresos_facturados,
    cobros_reales: r.cobros_reales,
  }));

  const hasData = chartData.some(
    (r) => r.ingresos_facturados > 0 || r.cobros_reales > 0,
  );

  if (loading) {
    return (
      <div className="dashboard-bento animate-pulse rounded-2xl p-6">
        <div className="mb-4 h-4 w-2/5 rounded bg-zinc-800" />
        <div className="h-[300px] rounded-xl bg-zinc-800/60" />
      </div>
    );
  }

  return (
    <div className="dashboard-bento rounded-2xl p-6">
      <h3 className="mb-1 text-sm font-semibold text-zinc-100">Tesorería: facturado vs cobrado</h3>
      <p className="mb-1 text-xs text-zinc-500">
        Ingresos facturados (emisión) frente a cobros reconocidos en el mismo mes (facturas marcadas como
        cobradas). El desfase refleja facturación pendiente de cobro.
      </p>
      <div className="mt-4 h-[min(260px,42vh)] min-h-[220px] w-full min-w-0 sm:h-[300px] sm:min-h-[260px]">
        {!hasData ? (
          <p className="py-16 text-center text-sm text-zinc-500">Sin datos de facturación en la ventana de 6 meses.</p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id={`${uid}-fac`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#059669" stopOpacity={0.45} />
                  <stop offset="95%" stopColor="#059669" stopOpacity={0} />
                </linearGradient>
                <linearGradient id={`${uid}-cob`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#52525b" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#52525b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                formatter={(value, name) => [
                  formatEUR(Number(value ?? 0)),
                  String(name),
                ]}
                labelFormatter={(_, payload) => {
                  const row = payload?.[0]?.payload as { periodo?: string } | undefined;
                  return row?.periodo ? `Periodo ${row.periodo}` : "";
                }}
                contentStyle={{
                  borderRadius: 12,
                  borderColor: "#3f3f46",
                  background: "#18181b",
                  fontSize: 12,
                  color: "#e4e4e7",
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }}
                formatter={(value) => <span className="text-zinc-400">{value}</span>}
              />
              <Area
                type="monotone"
                dataKey="ingresos_facturados"
                name="Ingresos facturados"
                stroke="#047857"
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#${uid}-fac)`}
              />
              <Area
                type="monotone"
                dataKey="cobros_reales"
                name="Cobros reales"
                stroke="#3f3f46"
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#${uid}-cob)`}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
