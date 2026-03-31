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
    <div className="ab-card p-5 rounded-2xl">
      <h3 className="text-base font-semibold text-slate-800">
        Break-even Analysis
      </h3>
      <p className="text-xs text-slate-500 mt-1">
        Area: gastos acumulados · Línea: ingresos acumulados
      </p>
      <div className="h-[300px] mt-3">
        {loading ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">
            Cargando break-even...
          </div>
        ) : rows.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">
            Sin datos financieros para calcular el punto de equilibrio.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="periodo" />
              <YAxis tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`} />
              <Tooltip
                formatter={(value: number | string, key: string) => {
                  const v = Number(value ?? 0);
                  if (key === "cumulative_ingresos") return [fmtEur(v), "Ingresos acumulados"];
                  if (key === "cumulative_gastos") return [fmtEur(v), "Gastos acumulados"];
                  return [String(value), key];
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

