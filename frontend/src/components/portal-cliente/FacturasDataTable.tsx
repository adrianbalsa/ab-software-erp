"use client";

import { useCallback, useMemo, useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, Download, FileCode2, Receipt } from "lucide-react";

import { PortalClienteAlert } from "@/components/portal-cliente/PortalClienteAlert";
import { PortalClienteEmptyState } from "@/components/portal-cliente/PortalClienteEmptyState";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import type { Catalog } from "@/i18n/catalog";
import { formatCurrencyEUR } from "@/i18n/localeFormat";
import { portalFacturaPdfUrl, portalFacturaXmlUrl, type PortalFacturaRow } from "@/lib/api";
import { portalDownloadFile } from "@/hooks/usePortalCliente";
import { cn } from "@/lib/utils";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface TableMeta<TData> {
    downloading: string | null;
    setDownloading: (v: string | null) => void;
    setError: (v: string | null) => void;
  }
}

function sortColumnAria(t: Catalog["pages"]["portalClienteFacturas"], columnTitle: string) {
  return t.sortByColumn.replace("{column}", columnTitle);
}

function mapEstadoPago(apiVal: string, t: Catalog["pages"]["portalClienteFacturas"]) {
  const s = apiVal.trim();
  if (s === "Pagada") return t.statusPaid;
  if (s === "Pendiente") return t.statusPending;
  return apiVal;
}

type Props = {
  rows: PortalFacturaRow[];
  className?: string;
};

export function FacturasDataTable({ rows, className }: Props) {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages.portalClienteFacturas;
  const fmtMoney = useCallback((n: number) => formatCurrencyEUR(n, locale), [locale]);

  const [sorting, setSorting] = useState<SortingState>([{ id: "fecha_emision", desc: true }]);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const columns = useMemo<ColumnDef<PortalFacturaRow>[]>(
    () => [
      {
        accessorKey: "numero_factura",
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-2 h-8 text-zinc-300 hover:text-white"
            aria-label={sortColumnAria(p, p.colNumber)}
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            {p.colNumber}
            <ArrowUpDown className="ml-1 size-3.5 opacity-60" aria-hidden />
          </Button>
        ),
        cell: ({ row }) => (
          <span className="font-mono text-xs font-medium text-zinc-100">{row.original.numero_factura}</span>
        ),
      },
      {
        accessorKey: "fecha_emision",
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-2 h-8 text-zinc-300 hover:text-white"
            aria-label={sortColumnAria(p, p.colEmission)}
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            {p.colEmission}
            <ArrowUpDown className="ml-1 size-3.5 opacity-60" aria-hidden />
          </Button>
        ),
        sortingFn: (a, b) => {
          const da = String(a.original.fecha_emision ?? "").slice(0, 10);
          const db = String(b.original.fecha_emision ?? "").slice(0, 10);
          return da.localeCompare(db);
        },
        cell: ({ row }) => (
          <span className="text-zinc-400">{String(row.original.fecha_emision ?? "").slice(0, 10) || "—"}</span>
        ),
      },
      {
        accessorKey: "total_factura",
        header: ({ column }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="-ml-2 h-8 text-zinc-300 hover:text-white"
            aria-label={sortColumnAria(p, p.colAmount)}
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            {p.colAmount}
            <ArrowUpDown className="ml-1 size-3.5 opacity-60" aria-hidden />
          </Button>
        ),
        cell: ({ row }) => (
          <span className="tabular-nums text-zinc-200">{fmtMoney(Number(row.original.total_factura))}</span>
        ),
      },
      {
        accessorKey: "estado_pago",
        enableSorting: false,
        header: p.colStatus,
        cell: ({ row }) => {
          const raw = row.original.estado_pago;
          const paid = raw === "Pagada";
          return (
            <span
              className={cn(
                "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold",
                paid ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-200",
              )}
            >
              {mapEstadoPago(raw, p)}
            </span>
          );
        },
      },
      {
        id: "docs",
        enableSorting: false,
        header: () => <span className="text-right">{p.colDocuments}</span>,
        cell: ({ row, table }) => {
          const id = row.original.id;
          const keyBase = `f-${id}`;
          const hasXml = row.original.xml_verifactu_disponible === true;
          const busy = table.options.meta?.downloading ?? null;
          return (
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                size="xs"
                variant="outline"
                className="border-zinc-600 bg-zinc-900/60 text-zinc-100 hover:bg-zinc-800"
                disabled={busy === `${keyBase}-pdf`}
                aria-busy={busy === `${keyBase}-pdf`}
                aria-label={`${p.pdf} ${row.original.numero_factura}`}
                onClick={async () => {
                  table.options.meta?.setError(null);
                  table.options.meta?.setDownloading(`${keyBase}-pdf`);
                  try {
                    await portalDownloadFile(portalFacturaPdfUrl(id), `factura-${id}.pdf`);
                  } catch (e) {
                    table.options.meta?.setError(e instanceof Error ? e.message : p.errPdfDownload);
                  } finally {
                    table.options.meta?.setDownloading(null);
                  }
                }}
              >
                <Download className="size-3.5" aria-hidden />
                {p.pdf}
              </Button>
              <Button
                type="button"
                size="xs"
                variant="outline"
                className="border-zinc-600 bg-zinc-900/60 text-zinc-100 hover:bg-zinc-800 disabled:opacity-40"
                disabled={!hasXml || busy === `${keyBase}-xml`}
                aria-busy={busy === `${keyBase}-xml`}
                aria-label={hasXml ? `${p.xml} ${row.original.numero_factura}` : p.xmlUnavailable}
                title={hasXml ? p.xmlTitle : p.xmlUnavailable}
                onClick={async () => {
                  if (!hasXml) return;
                  table.options.meta?.setError(null);
                  table.options.meta?.setDownloading(`${keyBase}-xml`);
                  try {
                    await portalDownloadFile(portalFacturaXmlUrl(id), `factura-${id}-verifactu.xml`);
                  } catch (e) {
                    table.options.meta?.setError(e instanceof Error ? e.message : p.errXmlDownload);
                  } finally {
                    table.options.meta?.setDownloading(null);
                  }
                }}
              >
                <FileCode2 className="size-3.5" aria-hidden />
                {p.xml}
              </Button>
            </div>
          );
        },
      },
    ],
    [p, fmtMoney],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    meta: {
      downloading,
      setDownloading,
      setError,
    },
  });

  return (
    <div className={cn("space-y-3", className)}>
      {error ? <PortalClienteAlert variant="panel">{error}</PortalClienteAlert> : null}
      <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950/40 shadow-sm">
        <Table>
          <caption className="sr-only">{p.tableCaption}</caption>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="border-zinc-800 hover:bg-transparent">
                {hg.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const ariaSort = header.column.getCanSort()
                    ? sorted === "asc"
                      ? "ascending"
                      : sorted === "desc"
                        ? "descending"
                        : "none"
                    : undefined;
                  return (
                    <TableHead key={header.id} className="text-zinc-400" aria-sort={ariaSort}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="border-zinc-800/80">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={columns.length} className="p-0">
                  <PortalClienteEmptyState
                    icon={Receipt}
                    title={p.empty}
                    description={p.emptyHint}
                    className="text-zinc-400 [&_p]:text-zinc-400"
                  />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
