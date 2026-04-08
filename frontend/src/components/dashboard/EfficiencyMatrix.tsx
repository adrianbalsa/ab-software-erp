"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

type Props = {
  loading: boolean;
  margenNetoKm: number | null;
  co2PerTonKm: number | null;
  ingresosMensuales: number;
};

type MatrixRow = {
  label: string;
  margen_neto_km: number;
  co2_per_ton_km: number;
  ingresos: number;
};

function fmtEur(v: number): string {
  return v.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  });
}

export function EfficiencyMatrix({
  loading,
  margenNetoKm,
  co2PerTonKm,
  ingresosMensuales,
}: Props) {
  const hasData = margenNetoKm != null && co2PerTonKm != null;
  const data: MatrixRow[] = hasData
    ? [
        {
          label: "Mes actual",
          margen_neto_km: Number(margenNetoKm),
          co2_per_ton_km: Number(co2PerTonKm),
          ingresos: Number.isFinite(ingresosMensuales) ? ingresosMensuales : 0,
        },
      ]
    : [];

  return (
    <div className="dashboard-bento rounded-2xl p-5">
      <h3 className="text-base font-semibold text-zinc-100">Efficiency Matrix (Margen vs CO2)</h3>
      <p className="mt-1 text-xs text-zinc-500">
        X: margen neto/km · Y: CO2 por ton-km · Burbuja: ingresos mensuales
      </p>

      <div className="mt-3 h-[300px]">
        {loading ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">Cargando matriz...</div>
        ) : data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            Sin datos de eficiencia para el periodo.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
              <XAxis
                type="number"
                dataKey="margen_neto_km"
                name="Margen neto/km"
                unit=" €/km"
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="co2_per_ton_km"
                name="CO2 por ton-km"
                unit=" kg"
                tick={{ fill: "#a1a1aa", fontSize: 11 }}
              />
              <ZAxis type="number" dataKey="ingresos" range={[100, 1400]} name="Ingresos" />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{
                  borderRadius: 12,
                  borderColor: "#3f3f46",
                  background: "#18181b",
                  fontSize: 12,
                  color: "#e4e4e7",
                }}
                formatter={(value: any, name: any) => {
                  const v = Number(value ?? 0);
                  if (name === "ingresos") return [fmtEur(v), "Ingresos"];
                  if (name === "margen_neto_km") return [`${v.toFixed(4)} €/km`, "Margen neto/km"];
                  if (name === "co2_per_ton_km") return [`${v.toFixed(4)} kg`, "CO2 por ton-km"];
                  return [String(value), name];
                }}
              />
              <Scatter data={data} fill="#34d399" />
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

