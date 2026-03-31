"use client";

import {
  Bubble,
  BubbleChart,
  CartesianGrid,
  ResponsiveContainer,
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
    <div className="ab-card p-5 rounded-2xl">
      <h3 className="text-base font-semibold text-slate-800">
        Efficiency Matrix (Margen vs CO2)
      </h3>
      <p className="text-xs text-slate-500 mt-1">
        X: margen neto/km · Y: CO2 por ton-km · Burbuja: ingresos mensuales
      </p>

      <div className="h-[300px] mt-3">
        {loading ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">
            Cargando matriz...
          </div>
        ) : data.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">
            Sin datos de eficiencia para el periodo.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BubbleChart margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="margen_neto_km"
                name="Margen neto/km"
                unit=" €/km"
              />
              <YAxis
                type="number"
                dataKey="co2_per_ton_km"
                name="CO2 por ton-km"
                unit=" kg"
              />
              <ZAxis type="number" dataKey="ingresos" range={[100, 1400]} name="Ingresos" />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(value: number | string, key: string) => {
                  const v = Number(value ?? 0);
                  if (key === "ingresos") return [fmtEur(v), "Ingresos"];
                  if (key === "margen_neto_km") return [`${v.toFixed(4)} €/km`, "Margen neto/km"];
                  if (key === "co2_per_ton_km") return [`${v.toFixed(4)} kg`, "CO2 por ton-km"];
                  return [String(value), key];
                }}
              />
              <Bubble data={data} dataKey="ingresos" fill="#2563eb" />
            </BubbleChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

