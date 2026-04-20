"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProfitMarginAnalytics, ProfitMarginTotals } from "@/lib/api";
import { downloadProfitMarginCsv } from "@/lib/profitMarginCsv";

const fmtEur = (n: number) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(n);

type WaterfallRow = { step: string; value: number; fill: string };

function totalsToWaterfallRows(t: ProfitMarginTotals): WaterfallRow[] {
  const { ingresos_totales: I, gastos_combustible: C, gastos_peajes: P, gastos_otros: O, margen_neto: M } = t;
  return [
    { step: "Ingresos", value: I, fill: "#10b981" },
    { step: "Combustible", value: -C, fill: "#f59e0b" },
    { step: "Peajes", value: -P, fill: "#38bdf8" },
    { step: "Otros", value: -O, fill: "#a78bfa" },
    { step: "Margen neto", value: M, fill: M >= 0 ? "#22c55e" : "#f43f5e" },
  ];
}

type TooltipProps = {
  active?: boolean;
  payload?: ReadonlyArray<{ value?: number; payload?: WaterfallRow }>;
};

function WaterfallTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload as WaterfallRow | undefined;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 p-3 text-xs text-zinc-100 shadow-lg">
      <p className="font-semibold">{p.step}</p>
      <p className="mt-1 font-mono text-emerald-200">{fmtEur(p.value)}</p>
    </div>
  );
}

export type MarginWaterfallChartProps = {
  analytics: ProfitMarginAnalytics;
  title?: string;
  description?: string;
  csvFilename: string;
};

/**
 * Desglose tipo waterfall vía barras positivas/negativas (Recharts no expone waterfall nativo).
 * Accesibilidad Fase 8: región con `aria-label` y descripción breve.
 */
export function MarginWaterfallChart({
  analytics,
  title = "Desglose de margen (rango)",
  description = "Ingresos de portes frente a gastos por categoría y margen neto (EUR, redondeo HALF_EVEN en servidor).",
  csvFilename,
}: MarginWaterfallChartProps) {
  const data = useMemo(() => totalsToWaterfallRows(analytics.totals_rango), [analytics.totals_rango]);
  const chartSummary = useMemo(() => {
    const t = analytics.totals_rango;
    return `Ingresos ${fmtEur(t.ingresos_totales)}, gastos totales ${fmtEur(t.gastos_totales)}, margen neto ${fmtEur(t.margen_neto)}.`;
  }, [analytics.totals_rango]);

  return (
    <Card className="bunker-card border-zinc-800">
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="text-zinc-100">{title}</CardTitle>
          <CardDescription className="text-zinc-400">{description}</CardDescription>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0 border-zinc-600 text-zinc-200 hover:bg-zinc-800"
          onClick={() => downloadProfitMarginCsv(analytics, csvFilename)}
          aria-label="Exportar serie de márgenes y totales a CSV para integraciones y webhooks"
        >
          Exportar CSV
        </Button>
      </CardHeader>
      <CardContent className="h-[min(55vh,420px)] min-h-[320px] w-full p-2 sm:p-4">
        <p id="margin-waterfall-summary" className="sr-only">
          {chartSummary} Use el botón Exportar CSV para obtener la serie completa con el mismo esquema que los webhooks
          automáticos.
        </p>
        <div
          role="img"
          aria-labelledby="margin-waterfall-title"
          aria-describedby="margin-waterfall-summary"
          className="h-full w-full"
        >
          <p id="margin-waterfall-title" className="sr-only">
            Gráfico de barras: desglose de ingresos, gastos por categoría y margen neto
          </p>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 28, right: 12, left: 4, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
              <XAxis dataKey="step" tick={{ fill: "#a1a1aa", fontSize: 11 }} interval={0} angle={-18} textAnchor="end" height={64} />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
                tickFormatter={(v) => fmtEur(Number(v))}
                width={72}
                label={{ value: "EUR", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 11 }}
              />
              <Tooltip content={<WaterfallTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {data.map((entry) => (
                  <Cell key={entry.step} fill={entry.fill} />
                ))}
                <LabelList
                  dataKey="value"
                  position="top"
                  formatter={(v: unknown) => fmtEur(Number(v))}
                  fill="#e4e4e7"
                  fontSize={10}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
