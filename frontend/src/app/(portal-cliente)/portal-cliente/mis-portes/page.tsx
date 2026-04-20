"use client";

import { useMemo, useState } from "react";
import { Activity, FileText, History, MapPin, Package, RefreshCw } from "lucide-react";
import Link from "next/link";

import { PortalClienteAlert } from "@/components/portal-cliente/PortalClienteAlert";
import { PortalClienteEmptyState } from "@/components/portal-cliente/PortalClienteEmptyState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { formatPortalDateTime } from "@/lib/portalLocaleFormat";
import { portalAlbaranPdfUrl, portalPorteCertificadoEsgUrl } from "@/lib/api";
import { portalDownloadFile, usePortalPortesActivos, usePortalPortesEntregados } from "@/hooks/usePortalCliente";
import { cn } from "@/lib/utils";
import type { Catalog } from "@/i18n/catalog";

function labelEstado(
  raw: string,
  estados: Catalog["pages"]["portalClienteMisPortes"]["estados"],
): string {
  const k = String(raw || "").trim().toLowerCase();
  if (k === "pendiente") return estados.pendiente;
  if (k === "facturado") return estados.facturado;
  if (k === "entregado") return estados.entregado;
  if (k) return raw;
  return estados.otros;
}

export default function MisPortesPage() {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages.portalClienteMisPortes;
  const activos = usePortalPortesActivos({ pollMs: 40_000 });
  const historico = usePortalPortesEntregados();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loading = activos.loading && activos.data.length === 0;
  const combinedError = err || activos.error || historico.error;

  const fmt = useMemo(
    () => (iso: string | null | undefined) => formatPortalDateTime(iso, locale, p.dateEmpty),
    [locale, p.dateEmpty],
  );

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{p.title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-600 dark:text-zinc-400">{p.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="hidden text-xs text-zinc-500 dark:text-zinc-500 sm:inline">{p.pollHint}</span>
          <Button
            asChild
            size="sm"
            variant="outline"
            className="border-zinc-300 dark:border-zinc-600"
          >
            <Link href="/portal/seguimiento" aria-label={p.mapViewAria}>
              <MapPin className="mr-1 size-3.5" aria-hidden />
              {p.mapView}
            </Link>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-zinc-300 dark:border-zinc-600"
            aria-label={p.refreshAria}
            onClick={() => void Promise.all([activos.refetch(), historico.refetch()])}
          >
            <RefreshCw className="mr-1 size-3.5" aria-hidden />
            {p.refresh}
          </Button>
        </div>
      </div>

      {combinedError ? <PortalClienteAlert>{combinedError}</PortalClienteAlert> : null}

      <Card className="border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
        <CardHeader className="border-b border-zinc-100 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" aria-hidden />
            <div>
              <CardTitle className="text-lg text-zinc-900 dark:text-zinc-50">{p.activeTitle}</CardTitle>
              <CardDescription className="dark:text-zinc-400">{p.activeDesc}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="overflow-x-auto rounded-lg border border-zinc-200/80 dark:border-zinc-800">
            <Table>
              <caption className="sr-only">{p.captionActive}</caption>
              <TableHeader>
                <TableRow className="border-zinc-200 hover:bg-zinc-50/80 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                  <TableHead scope="col">{p.thOrigin}</TableHead>
                  <TableHead scope="col">{p.thDestination}</TableHead>
                  <TableHead scope="col">{p.thPlannedDate}</TableHead>
                  <TableHead scope="col">{p.thStatus}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="py-10 text-center text-zinc-500">
                      <div role="status" aria-live="polite">
                        {p.loading}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : activos.data.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="p-0">
                      <PortalClienteEmptyState
                        icon={Package}
                        title={p.emptyActive}
                        description={p.emptyActiveHint}
                      />
                    </TableCell>
                  </TableRow>
                ) : (
                  activos.data.map((row) => (
                    <TableRow key={String(row.id)} className="border-zinc-100 dark:border-zinc-800/80">
                      <TableCell className="font-medium text-zinc-900 dark:text-zinc-100">{row.origen}</TableCell>
                      <TableCell className="text-zinc-700 dark:text-zinc-300">{row.destino}</TableCell>
                      <TableCell className="text-zinc-600 dark:text-zinc-400">{fmt(row.fecha)}</TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold capitalize",
                            String(row.estado).toLowerCase() === "pendiente"
                              ? "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-200"
                              : "bg-sky-100 text-sky-900 dark:bg-sky-500/15 dark:text-sky-200",
                          )}
                        >
                          {labelEstado(String(row.estado), p.estados)}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card className="border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
        <CardHeader className="border-b border-zinc-100 dark:border-zinc-800">
          <CardTitle className="text-lg text-zinc-900 dark:text-zinc-50">{p.historicTitle}</CardTitle>
          <CardDescription className="dark:text-zinc-400">{p.historicDesc}</CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="overflow-x-auto rounded-lg border border-zinc-200/80 dark:border-zinc-800">
            <Table>
              <caption className="sr-only">{p.captionHistoric}</caption>
              <TableHeader>
                <TableRow className="border-zinc-200 hover:bg-zinc-50/80 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                  <TableHead scope="col">{p.thOrigin}</TableHead>
                  <TableHead scope="col">{p.thDestination}</TableHead>
                  <TableHead scope="col">{p.thDelivery}</TableHead>
                  <TableHead scope="col" className="text-right">
                    {p.thDocuments}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historico.loading && historico.data.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="py-10 text-center text-zinc-500">
                      <div role="status" aria-live="polite">
                        {p.loadingHistoric}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : historico.data.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="p-0">
                      <PortalClienteEmptyState
                        icon={History}
                        title={p.emptyHistoric}
                        description={p.emptyHistoricHint}
                      />
                    </TableCell>
                  </TableRow>
                ) : (
                  historico.data.map((row) => (
                    <TableRow key={String(row.id)} className="border-zinc-100 dark:border-zinc-800/80">
                      <TableCell className="font-medium text-zinc-900 dark:text-zinc-100">{row.origen}</TableCell>
                      <TableCell className="text-zinc-700 dark:text-zinc-300">{row.destino}</TableCell>
                      <TableCell className="text-zinc-600 dark:text-zinc-400">{fmt(row.fecha_entrega)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            className="border-emerald-600/40 bg-emerald-50/80 text-emerald-900 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-100 dark:hover:bg-emerald-900/30"
                            disabled={busy === `pod-${row.id}`}
                            aria-busy={busy === `pod-${row.id}`}
                            onClick={async () => {
                              setErr(null);
                              setBusy(`pod-${row.id}`);
                              try {
                                await portalDownloadFile(portalAlbaranPdfUrl(row.id), `albaran-${row.id}.pdf`);
                              } catch (e) {
                                setErr(e instanceof Error ? e.message : p.errPodDownload);
                              } finally {
                                setBusy(null);
                              }
                            }}
                          >
                            <FileText className="mr-1 size-3.5" aria-hidden />
                            {p.btnPod}
                          </Button>
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            className="border-zinc-300 dark:border-zinc-600"
                            disabled={busy === `esg-${row.id}`}
                            aria-busy={busy === `esg-${row.id}`}
                            onClick={async () => {
                              setErr(null);
                              setBusy(`esg-${row.id}`);
                              try {
                                await portalDownloadFile(
                                  portalPorteCertificadoEsgUrl(row.id),
                                  `certificado-esg-${row.id}.pdf`,
                                );
                              } catch (e) {
                                setErr(e instanceof Error ? e.message : p.errCertDownload);
                              } finally {
                                setBusy(null);
                              }
                            }}
                          >
                            {p.btnCertGlec}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
