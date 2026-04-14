"use client";

import { ShieldCheck } from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { RiskRankingRow } from "@/lib/api";

function formatEUR(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  });
}

/** Severidad 0–1 dentro del lote (amarillo → rojo). */
function riskBarColor(severity01: number): string {
  const t = Math.min(1, Math.max(0, severity01));
  const hue = 52 - t * 52;
  return `hsl(${hue} 88% 42%)`;
}

type Props = {
  rows: RiskRankingRow[];
};

export function RiskRankingTable({ rows }: Props) {
  const maxVr = Math.max(0, ...rows.map((r) => r.valor_riesgo), 1e-9);

  if (rows.length === 0) {
    return (
      <p className="text-sm text-zinc-500 py-4">
        No hay clientes con saldo pendiente para el ranking de riesgo.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Cliente</TableHead>
          <TableHead className="text-right">Saldo pendiente</TableHead>
          <TableHead className="text-right">Score de riesgo</TableHead>
          <TableHead className="min-w-[200px]">
            Valor en riesgo (<span className="font-serif italic">V</span>
            <sub className="text-[10px]">r</sub>)
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          const severity = maxVr > 0 ? row.valor_riesgo / maxVr : 0;
          const barPct = Math.min(100, severity * 100);
          const fill = riskBarColor(severity);

          return (
            <TableRow key={row.cliente_id}>
              <TableCell className="font-medium text-zinc-100">
                <span className="inline-flex items-center gap-2">
                  {row.mandato_sepa_activo ? (
                    <span title="Mandato SEPA activo" className="inline-flex">
                      <ShieldCheck
                        className="h-4 w-4 shrink-0 text-emerald-500"
                        aria-label="Mandato SEPA activo"
                      />
                    </span>
                  ) : null}
                  {row.nombre}
                </span>
              </TableCell>
              <TableCell className="text-right tabular-nums text-zinc-300">
                {formatEUR(row.saldo_pendiente)}
              </TableCell>
              <TableCell className="text-right tabular-nums text-zinc-300">
                {row.riesgo_score.toLocaleString("es-ES", { maximumFractionDigits: 2 })}
              </TableCell>
              <TableCell>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-xs text-zinc-500">
                    <span className="tabular-nums font-medium text-zinc-200">
                      {formatEUR(row.valor_riesgo)}
                    </span>
                  </div>
                  <Progress
                    value={barPct}
                    className="h-2.5 bg-zinc-800/90"
                    indicatorClassName="shadow-sm"
                    indicatorStyle={{ backgroundColor: fill }}
                  />
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
