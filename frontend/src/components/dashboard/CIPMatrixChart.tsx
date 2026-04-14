"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";
import { useChartPerformance } from "@/hooks/useChartPerformance";
import { api, type CIPMatrixPoint } from "@/lib/api";
import { Loader2 } from "lucide-react";
// Formatting helpers
const formatCurrency = (value: number) =>
  new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);

const formatNumber = (value: number) =>
  new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(value);

type CipTooltipPayload = { payload?: CIPMatrixPoint };

type CipScatterTooltipProps = {
  active?: boolean;
  payload?: ReadonlyArray<CipTooltipPayload>;
};

// Custom tooltip for the ScatterChart
const CustomTooltip = ({ active, payload }: CipScatterTooltipProps) => {
  if (active && payload && payload.length) {
    const first = payload[0] as CipTooltipPayload | undefined;
    const data = first?.payload;
    if (!data) return null;
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 p-4 shadow-xl shadow-black/40 backdrop-blur-sm">
        <p className="mb-3 border-b border-zinc-800 pb-2 font-semibold text-zinc-100">
          {data.ruta}
        </p>
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between gap-4">
            <span className="text-zinc-400">Margen Neto:</span>
            <span className="font-medium text-emerald-500">
              {formatCurrency(data.margen_neto)}
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-zinc-400">Emisiones CO₂:</span>
            <span className="font-medium text-rose-400">
              {formatNumber(data.emisiones_co2)} kg
            </span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-zinc-400">Volumen:</span>
            <span className="font-medium text-zinc-200">
              {data.total_portes} portes
            </span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

type CIPMatrixChartProps = {
  /** Altura del contenedor del gráfico (p. ej. min-h para página completa). */
  className?: string;
};

export function CIPMatrixChart({ className }: CIPMatrixChartProps) {
  const { staticCharts, isNarrow } = useChartPerformance();
  const [data, setData] = useState<CIPMatrixPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const axisTick = isNarrow ? 10 : 12;
  const tickCount = isNarrow ? 4 : 6;

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        setError(null);
        const result = await api.analytics.getCIPMatrix();
        setData(result);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Error al cargar datos de la Matriz CIP");
      } finally {
        setIsLoading(false);
      }
    }
    void loadData();
  }, []);

  const shell = (inner: ReactNode) => (
    <div className={className ?? "w-full min-h-[400px]"}>{inner}</div>
  );

  if (isLoading) {
    return shell(
      <div className="flex min-h-[400px] w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-500/80" />
      </div>,
    );
  }

  if (error || !data || data.length === 0) {
    return shell(
      <div className="flex min-h-[400px] w-full items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-900/30">
        <p className="text-sm text-zinc-400">
          {error || "No hay suficientes datos (se requieren rutas con múltiples portes)."}
        </p>
      </div>,
    );
  }

  // Calculate averages to draw quadrants
  const avgMargin =
    data.reduce((sum, item) => sum + item.margen_neto, 0) / data.length;
  const avgEmissions =
    data.reduce((sum, item) => sum + item.emisiones_co2, 0) / data.length;

  return shell(
    <div className="h-[min(70vh,640px)] w-full min-h-[520px]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart
          margin={{
            top: 20,
            right: 20,
            bottom: 20,
            left: 20,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          
          <XAxis 
            type="number" 
            dataKey="margen_neto" 
            name="Margen Neto" 
            tickFormatter={(value) => `${value}€`}
            stroke="#94a3b8"
            fontSize={axisTick}
            tickMargin={10}
            tickCount={tickCount}
          />
          
          <YAxis 
            type="number" 
            dataKey="emisiones_co2" 
            name="Emisiones CO2" 
            tickFormatter={(value) => `${formatNumber(value)} kg`}
            stroke="#94a3b8"
            fontSize={axisTick}
            tickMargin={10}
            width={isNarrow ? 64 : 80}
            tickCount={tickCount}
          />
          
          <ZAxis 
            type="number" 
            dataKey="total_portes" 
            range={[60, 400]} 
            name="Portes" 
          />
          
          <Tooltip 
            content={<CustomTooltip />} 
            cursor={{ strokeDasharray: '3 3', stroke: '#cbd5e1' }}
          />

          {/* Quadrant dividing lines */}
          <ReferenceLine 
            y={avgEmissions} 
            stroke="#cbd5e1" 
            strokeDasharray="3 3" 
            label={{ value: 'CO₂ Promedio', position: 'insideTopLeft', fill: '#94a3b8', fontSize: isNarrow ? 9 : 11 }}
          />
          <ReferenceLine 
            x={avgMargin} 
            stroke="#cbd5e1" 
            strokeDasharray="3 3" 
            label={{ value: 'Margen Promedio', position: 'insideTopRight', fill: '#94a3b8', fontSize: isNarrow ? 9 : 11 }}
          />

          <Scatter name="Rutas" data={data} isAnimationActive={!staticCharts}>
            {data.map((entry, index) => {
              // Determine color based on quadrant
              // Ideal: High Margin (> avg), Low Emissions (< avg)
              const isHighMargin = entry.margen_neto >= avgMargin;
              const isLowEmissions = entry.emisiones_co2 <= avgEmissions;
              
              let fill = "#94a3b8"; // Default slate-400
              
              if (isHighMargin && isLowEmissions) {
                fill = "#10b981"; // Emerald-500 (Star routes)
              } else if (!isHighMargin && !isLowEmissions) {
                fill = "#f43f5e"; // Rose-500 (Problem routes)
              } else if (isHighMargin && !isLowEmissions) {
                fill = "#f59e0b"; // Amber-500 (Profitable but dirty)
              } else if (!isHighMargin && isLowEmissions) {
                fill = "#3b82f6"; // Blue-500 (Clean but low profit)
              }

              return <Cell key={`cell-${index}`} fill={fill} fillOpacity={0.7} stroke={fill} strokeWidth={1} />;
            })}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>,
  );
}
