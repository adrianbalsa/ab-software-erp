"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useChartPerformance } from "@/hooks/useChartPerformance";

import { TruckEfficiency } from "./FleetEfficiencyTable";

interface TruckProfitChartProps {
  data: TruckEfficiency[];
}

export function TruckProfitChart({ data }: TruckProfitChartProps) {
  const { staticCharts, isNarrow } = useChartPerformance();

  // Prepara los datos para el gráfico: Ingresos vs Gastos
  // Margen = Ingresos - Gastos => Ingresos = Margen + Gastos
  // Gastos = litros * precio_litro (asumiendo que los gastos son principalmente de combustible o costes varios que ya calculamos)
  // Como tenemos coste_por_km y km_totales, Gastos = coste_por_km * km_totales
  const chartData = data.map((truck) => {
    const gastos = truck.coste_por_km * truck.km_totales;
    const ingresos = truck.margen_generado + gastos;
    
    return {
      name: truck.matricula,
      Ingresos: Math.round(ingresos),
      Gastos: Math.round(gastos),
      Margen: Math.round(truck.margen_generado),
    };
  });

  // Ordenar por ingresos descendente
  chartData.sort((a, b) => b.Ingresos - a.Ingresos);

  return (
    <div className="h-[350px] w-full border rounded-md p-4 bg-card">
      <h3 className="font-semibold text-lg mb-4">Ingresos vs Gastos por Vehículo</h3>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{
            top: 20,
            right: 30,
            left: 20,
            bottom: isNarrow ? 28 : 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} vertical={false} />
          <XAxis 
            dataKey="name" 
            tick={{ fontSize: isNarrow ? 10 : 12 }}
            angle={isNarrow ? -35 : 0}
            textAnchor={isNarrow ? "end" : "middle"}
            height={isNarrow ? 48 : 30}
            interval={isNarrow ? 1 : 0}
            axisLine={false}
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: isNarrow ? 10 : 12 }}
            axisLine={false}
            tickLine={false}
            tickCount={isNarrow ? 5 : undefined}
            tickFormatter={(value) => `${value / 1000}k`}
          />
          <Tooltip 
            formatter={(value: unknown) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(value) || 0)}
            cursor={{ fill: 'rgba(0,0,0,0.05)' }}
            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
          />
          <Legend />
          <Bar
            dataKey="Ingresos"
            fill="hsl(var(--chart-2, 142.1 76.2% 36.3%))"
            radius={[4, 4, 0, 0]}
            isAnimationActive={!staticCharts}
          />
          <Bar
            dataKey="Gastos"
            fill="hsl(var(--chart-1, 0 84.2% 60.2%))"
            radius={[4, 4, 0, 0]}
            isAnimationActive={!staticCharts}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
