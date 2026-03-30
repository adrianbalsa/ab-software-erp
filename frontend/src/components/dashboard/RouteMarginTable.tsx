"use client";

import { AlertTriangle } from "lucide-react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { RouteMarginRow } from "@/lib/api";

function formatEUR2(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPct(value: number) {
  return `${value.toLocaleString("es-ES", { maximumFractionDigits: 2 })}%`;
}

type Props = {
  rows: RouteMarginRow[];
};

export function RouteMarginTable({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-zinc-500 py-4">
        No hay rutas con suficientes viajes para el ranking de margen (mínimo 2 portes por ruta).
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ruta</TableHead>
          <TableHead className="text-right">Viajes</TableHead>
          <TableHead className="text-right">Ingresos</TableHead>
          <TableHead className="text-right">Costes</TableHead>
          <TableHead className="text-right">Margen neto</TableHead>
          <TableHead className="text-right">Margen %</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => {
          const negative = row.margen_neto < 0;
          const strongPositive = row.margen_porcentual > 15;

          return (
            <TableRow key={`${row.ruta}-${i}`}>
              <TableCell className="font-medium text-zinc-900 max-w-[260px] truncate" title={row.ruta}>
                {row.ruta}
              </TableCell>
              <TableCell className="text-right tabular-nums text-zinc-700">
                {row.total_portes.toLocaleString("es-ES")}
              </TableCell>
              <TableCell className="text-right tabular-nums text-zinc-700">
                {formatEUR2(row.ingresos_totales)}
              </TableCell>
              <TableCell className="text-right tabular-nums text-zinc-700">
                {formatEUR2(row.costes_totales)}
              </TableCell>
              <TableCell
                className={`text-right tabular-nums font-medium ${
                  negative
                    ? "text-red-600 dark:text-red-500"
                    : strongPositive
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-zinc-900"
                }`}
              >
                <span className="inline-flex items-center justify-end gap-1.5">
                  {negative ? (
                    <AlertTriangle
                      className="h-4 w-4 shrink-0 text-red-600 dark:text-red-500"
                      aria-label="Margen negativo"
                    />
                  ) : null}
                  {formatEUR2(row.margen_neto)}
                </span>
              </TableCell>
              <TableCell
                className={`text-right tabular-nums ${
                  negative
                    ? "text-red-600 dark:text-red-500"
                    : strongPositive
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-zinc-700"
                }`}
              >
                {formatPct(row.margen_porcentual)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
