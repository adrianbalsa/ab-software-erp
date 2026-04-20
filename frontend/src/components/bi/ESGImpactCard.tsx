"use client";

import { Leaf } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProfitMarginEsgMoM } from "@/lib/api";

const fmt = (n: number, digits = 2) =>
  new Intl.NumberFormat("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);

export type ESGImpactCardProps = {
  esg: ProfitMarginEsgMoM | null | undefined;
  title?: string;
};

/**
 * Comparativa de emisiones equivalentes (combustible) mes vs mes anterior,
 * usando el factor ISO 14083 (2,67 kg CO₂e / L) devuelto por la API.
 */
export function ESGImpactCard({
  esg,
  title = "Impacto CO₂ (combustible)",
}: ESGImpactCardProps) {
  if (!esg) {
    return (
      <Card className="bunker-card border-zinc-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-100">
            <Leaf className="h-5 w-5 text-emerald-400" aria-hidden />
            {title}
          </CardTitle>
          <CardDescription className="text-zinc-500">Sin datos de combustible para los meses de referencia.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const factor = esg.iso_14083_kg_co2_per_litre;
  const saved = esg.co2_saved_vs_previous_kg;

  return (
    <Card className="bunker-card border-emerald-900/40 bg-gradient-to-br from-emerald-950/30 to-zinc-950">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-zinc-100">
          <Leaf className="h-5 w-5 text-emerald-400" aria-hidden />
          {title}
        </CardTitle>
        <CardDescription className="text-zinc-400">
          Mes ancla {esg.anchor_month} vs {esg.previous_month}. Factor diésel ISO 14083:{" "}
          <span className="font-mono text-emerald-200/90">{fmt(factor, 2)} kg/L</span> (litros implícitos desde tickets
          combustible).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          role="group"
          aria-label={`Ahorro de emisiones respecto al mes anterior: ${fmt(saved, 3)} kilogramos de CO2 equivalente`}
          className="grid gap-4 sm:grid-cols-2"
        >
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">CO₂ mes actual</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-50">{fmt(esg.co2_kg_current, 3)} kg</p>
            <p className="mt-1 text-xs text-zinc-500">Litros implícitos: {fmt(esg.litros_implied_current, 2)} L</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">CO₂ mes anterior</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-300">{fmt(esg.co2_kg_previous, 3)} kg</p>
            <p className="mt-1 text-xs text-zinc-500">Litros implícitos: {fmt(esg.litros_implied_previous, 2)} L</p>
          </div>
        </div>
        <p className="mt-6 rounded-lg border border-emerald-800/50 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-100">
          <strong className="font-semibold">Reducción vs mes anterior:</strong>{" "}
          <span className="font-mono text-lg text-emerald-300">{fmt(saved, 3)} kg CO₂e</span>
        </p>
      </CardContent>
    </Card>
  );
}
