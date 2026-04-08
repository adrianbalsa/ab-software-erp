"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type MonthlyPoint = {
  periodo: string;
  ingresos: number;
  gastos: number;
};

type BreakEvenRow = {
  periodo: string;
  cumulative_ingresos: number;
  cumulative_gastos: number;
};

type TooltipValue = number | string | ReadonlyArray<number | string> | null | undefined;

type Props = {
  loading: boolean;
  monthly: MonthlyPoint[];
};

function fmtEur(v: number): string {
  return v.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

export function BreakEvenAnalysis({ loading, monthly }: Props) {
  const rows: BreakEvenRow[] = [];
  let accIngresos = 0;
  let accGastos = 0;
  for (const p of monthly) {
    accIngresos += Number(p.ingresos ?? 0);
    accGastos += Number(p.gastos ?? 0);
    rows.push({
      periodo: p.periodo,
      cumulative_ingresos: accIngresos,
      cumulative_gastos: accGastos,
    });
  }

  const breakEven =
    rows.find((r) => r.cumulative_ingresos >= r.cumulative_gastos) ?? null;

  return (
    <div className="dashboard-bento rounded-2xl p-5">
      <h3 className="text-base font-semibold text-zinc-100">Break-even Analysis</h3>
      <p className="mt-1 text-xs text-zinc-500">Area: gastos acumulados · Línea: ingresos acumulados</p>
      <div className="mt-3 h-[300px]">
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            Cargando break-even...
          </div>
        ) : rows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            Sin datos financieros para calcular el punto de equilibrio.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
              <XAxis dataKey="periodo" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 12,
                  borderColor: "#3f3f46",
                  background: "#18181b",
                  fontSize: 12,
                  color: "#e4e4e7",
                }}
                formatter={(value: TooltipValue, name: string | number | undefined) => {
                  const v = Number(value ?? 0);
                  if (name === "cumulative_ingresos") return [fmtEur(v), "Ingresos acumulados"];
                  if (name === "cumulative_gastos") return [fmtEur(v), "Gastos acumulados"];
                  return [String(value), name];
                }}
              />
              <Area
                type="monotone"
                dataKey="cumulative_gastos"
                name="Gastos acumulados"
                fill="#f59e0b"
                fillOpacity={0.22}
                stroke="#d97706"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="cumulative_ingresos"
                name="Ingresos acumulados"
                stroke="#16a34a"
                strokeWidth={3}
                dot={false}
              />
              {breakEven ? (
                <ReferenceDot
                  x={breakEven.periodo}
                  y={breakEven.cumulative_ingresos}
                  r={6}
                  fill="#dc2626"
                  stroke="#991b1b"
                  ifOverflow="visible"
                />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

