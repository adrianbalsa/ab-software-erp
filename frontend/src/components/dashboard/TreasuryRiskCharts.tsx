"use client";

import {
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

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type TrendPoint = {
  periodo: string;
  cobrado: number;
  pendiente: number;
};

export type TreasuryRiskChartsProps = {
  totalPending: number;
  sepaGuaranteed: number;
  highRisk: number;
  trendData: TrendPoint[];
};

function formatEUR(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function formatMonthLabel(periodo: string) {
  const [year, month] = periodo.split("-").map(Number);
  if (!year || !month) return periodo;
  return new Date(year, month - 1, 1).toLocaleDateString("es-ES", {
    month: "short",
  });
}

export function TreasuryRiskCharts({
  totalPending,
  sepaGuaranteed,
  highRisk,
  trendData,
}: TreasuryRiskChartsProps) {
  const normalizedTotal = Math.max(0, totalPending);
  const guaranteed = Math.max(0, Math.min(sepaGuaranteed, normalizedTotal));
  const high = Math.max(0, Math.min(highRisk, normalizedTotal));
  const moderate = Math.max(0, normalizedTotal - guaranteed - high);

  const debtExposureData = [
    { name: "Garantizado SEPA", value: guaranteed, fill: "#16a34a" },
    { name: "Riesgo Alto", value: high, fill: "#dc2626" },
    { name: "Riesgo Moderado", value: moderate, fill: "#f59e0b" },
  ];

  const cashflowData = trendData.map((row) => ({
    ...row,
    mes: formatMonthLabel(row.periodo),
  }));

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card className="bunker-card">
        <CardHeader>
          <CardTitle className="text-zinc-100">Exposicion de la Deuda</CardTitle>
          <CardDescription className="text-zinc-400">
            Pendiente segmentado entre SEPA garantizado, riesgo alto y moderado.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px] w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={debtExposureData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={72}
                  outerRadius={110}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {debtExposureData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => formatEUR(Number(value ?? 0))}
                  contentStyle={{
                    borderRadius: 12,
                    borderColor: "#3f3f46",
                    background: "#18181b",
                    color: "#e4e4e7",
                    fontSize: 12,
                  }}
                />
                <Legend
                  layout="horizontal"
                  verticalAlign="bottom"
                  align="center"
                  wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="bunker-card">
        <CardHeader>
          <CardTitle className="text-zinc-100">Proyeccion de Cash Flow</CardTitle>
          <CardDescription className="text-zinc-400">
            Evolucion mensual en barras apiladas: cobrado y pendiente.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[320px] w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cashflowData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                <XAxis dataKey="mes" tick={{ fill: "#a1a1aa", fontSize: 11 }} tickLine={false} />
                <YAxis
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`}
                />
                <Tooltip
                  formatter={(value) => formatEUR(Number(value ?? 0))}
                  labelFormatter={(_, payload) => {
                    const row = payload?.[0]?.payload as { periodo?: string } | undefined;
                    return row?.periodo ?? "";
                  }}
                  contentStyle={{
                    borderRadius: 12,
                    borderColor: "#3f3f46",
                    background: "#18181b",
                    color: "#e4e4e7",
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "#a1a1aa" }} />
                <Bar dataKey="cobrado" name="Cobrado" stackId="cash" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar
                  dataKey="pendiente"
                  name="Pendiente"
                  stackId="cash"
                  fill="#9ca3af"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
