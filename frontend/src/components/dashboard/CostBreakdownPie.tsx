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
      <div className="dashboard-bento animate-pulse rounded-2xl p-6">
        <div className="mb-4 h-4 w-1/2 rounded bg-zinc-800" />
        <div className="h-[280px] rounded-xl bg-zinc-800/60" />
      </div>
    );
  }

  return (
    <div className="dashboard-bento rounded-2xl p-6">
      <h3 className="mb-1 text-sm font-semibold text-zinc-100">Desglose de gastos</h3>
      <p className="mb-4 text-xs text-zinc-500">Últimos 6 meses · categorías operativas (neto sin IVA)</p>
      <div className="h-[min(260px,40vh)] min-h-[220px] w-full min-w-0 sm:h-[280px] sm:min-h-[240px]">
        {chartData.length === 0 ? (
          <p className="py-14 text-center text-sm text-zinc-500">Sin gastos en el periodo para clasificar.</p>
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
  );
}
