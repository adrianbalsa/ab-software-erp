"use client";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { GastoBucketCinco } from "@/hooks/useFinanceDashboard";

/** Paleta Zinc / Esmeralda (landing AB Logistics) */
const BUCKET_FILL: Record<string, string> = {
  Combustible: "#059669",
  Personal: "#10b981",
  Mantenimiento: "#52525b",
  Seguros: "#a1a1aa",
  Peajes: "#047857",
};

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

export type CostBreakdownPieProps = {
  data: GastoBucketCinco[];
  loading?: boolean;
};

export function CostBreakdownPie({ data, loading }: CostBreakdownPieProps) {
  const chartData = data
    .map((d) => ({
      name: d.name,
      value: d.value,
      fill: BUCKET_FILL[d.name] ?? "#71717a",
    }))
    .filter((d) => d.value > 0);

  if (loading) {
    return (
      <div className="ab-card rounded-2xl p-6 animate-pulse">
        <div className="h-4 bg-zinc-200/90 rounded w-1/2 mb-4" />
        <div className="h-[280px] bg-zinc-100 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="ab-card rounded-2xl p-6">
      <h3 className="text-sm font-bold text-zinc-800 mb-1">
        Desglose de gastos
      </h3>
      <p className="text-xs text-zinc-500 mb-4">
        Últimos 6 meses · categorías operativas (neto sin IVA)
      </p>
      <div className="h-[280px] w-full min-w-0">
        {chartData.length === 0 ? (
          <p className="text-sm text-zinc-500 py-14 text-center">
            Sin gastos en el periodo para clasificar.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={64}
                outerRadius={96}
                paddingAngle={2}
                dataKey="value"
                nameKey="name"
                strokeWidth={0}
              >
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => formatEUR(Number(value ?? 0))}
                contentStyle={{
                  borderRadius: 12,
                  borderColor: "#e4e4e7",
                  fontSize: 12,
                }}
              />
              <Legend
                layout="horizontal"
                verticalAlign="bottom"
                align="center"
                wrapperStyle={{ fontSize: 11, color: "#52525b" }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
