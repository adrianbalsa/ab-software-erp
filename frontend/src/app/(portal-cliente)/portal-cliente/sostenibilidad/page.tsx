"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Award, Leaf, Trees } from "lucide-react";

import { PortalClienteAlert } from "@/components/portal-cliente/PortalClienteAlert";
import { PortalClienteEmptyState } from "@/components/portal-cliente/PortalClienteEmptyState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { formatPortalDecimal, intlLocaleForApp } from "@/lib/portalLocaleFormat";
import { portalEsgExportCsvUrl, portalPorteCertificadoEsgUrl } from "@/lib/api";
import { portalDownloadFile, usePortalEsgResumen, usePortalPortesEntregados } from "@/hooks/usePortalCliente";

export default function SostenibilidadPage() {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages.portalClienteSostenibilidad;
  const esg = usePortalEsgResumen();
  const portes = usePortalPortesEntregados();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const kg = esg.data?.co2_savings_ytd ?? 0;
  const chartData = useMemo(
    () => [{ name: p.chartBarLabel, kg: Math.max(kg, 0.0001) }],
    [kg, p.chartBarLabel],
  );
  const intlTag = intlLocaleForApp(locale);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{p.title}</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{p.subtitle}</p>
        <div className="mt-4">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="border-emerald-600/40 text-emerald-800 hover:bg-emerald-50 dark:border-emerald-500/40 dark:text-emerald-200 dark:hover:bg-emerald-950/40"
            aria-label={p.downloadCsvAria}
            onClick={async () => {
              setErr(null);
              try {
                await portalDownloadFile(portalEsgExportCsvUrl(), `esg_ytd_export.csv`);
              } catch (e) {
                setErr(e instanceof Error ? e.message : p.errCsv);
              }
            }}
          >
            {p.downloadCsv}
          </Button>
        </div>
      </div>

      {esg.error || portes.error || err ? (
        <PortalClienteAlert>{err || esg.error || portes.error}</PortalClienteAlert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Leaf className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
              <CardTitle className="text-lg text-zinc-900 dark:text-zinc-50">{p.co2Title}</CardTitle>
            </div>
            <CardDescription className="dark:text-zinc-400">
              {p.co2DescLead}
              {p.co2DescBody}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {esg.loading && !esg.data ? (
              <p className="text-sm text-zinc-500" role="status" aria-live="polite">
                {p.loadingMetrics}
              </p>
            ) : (
              <>
                <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 px-5 py-6 dark:border-emerald-900/40 dark:bg-emerald-950/30">
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
                    {p.ytdLabel}
                  </p>
                  <p className="mt-2 text-4xl font-semibold tabular-nums tracking-tight text-emerald-950 dark:text-emerald-50">
                    {formatPortalDecimal(kg, locale, 2)}
                    <span className="ml-2 text-lg font-medium text-emerald-800/90 dark:text-emerald-200/90">
                      {p.kgCo2e}
                    </span>
                  </p>
                </div>
                <div
                  className="h-52 w-full"
                  role="img"
                  aria-label={p.co2RegionLabel}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-zinc-200 dark:stroke-zinc-700" />
                      <XAxis dataKey="name" tick={{ fill: "currentColor", fontSize: 11 }} className="text-zinc-500" />
                      <YAxis
                        tick={{ fill: "currentColor", fontSize: 11 }}
                        className="text-zinc-500"
                        width={44}
                        tickFormatter={(v) => `${v}`}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: 8,
                          border: "1px solid rgba(63,63,70,0.4)",
                          background: "rgba(24,24,27,0.95)",
                          color: "#fafafa",
                        }}
                        formatter={(value) => {
                          const n = typeof value === "number" ? value : Number(value);
                          const safe = Number.isFinite(n) ? n : 0;
                          return [
                            `${safe.toLocaleString(intlTag, { maximumFractionDigits: 4 })} ${p.chartTooltipNumberUnit}`,
                            p.chartTooltipSaving,
                          ];
                        }}
                      />
                      <Bar dataKey="kg" radius={[6, 6, 0, 0]}>
                        <Cell fill="#10b981" />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-blue-600 dark:text-blue-400" aria-hidden />
              <CardTitle className="text-lg text-zinc-900 dark:text-zinc-50">{p.certTitle}</CardTitle>
            </div>
            <CardDescription className="dark:text-zinc-400">{p.certDesc}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto rounded-lg border border-zinc-200/80 dark:border-zinc-800">
              <Table>
                <caption className="sr-only">{p.captionCertTable}</caption>
                <TableHeader>
                  <TableRow className="border-zinc-200 hover:bg-zinc-50/80 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                    <TableHead scope="col">{p.thRoute}</TableHead>
                    <TableHead scope="col" className="text-right">
                      {p.thCertificate}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {portes.loading && portes.data.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={2} className="py-8 text-center text-zinc-500">
                        <div role="status" aria-live="polite">
                          {p.loadingPortes}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : portes.data.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={2} className="p-0">
                        <PortalClienteEmptyState
                          icon={Trees}
                          title={p.emptyPortes}
                          description={p.emptyPortesHint}
                        />
                      </TableCell>
                    </TableRow>
                  ) : (
                    portes.data.map((row) => (
                      <TableRow key={String(row.id)} className="border-zinc-100 dark:border-zinc-800/80">
                        <TableCell>
                          <p className="font-medium text-zinc-900 dark:text-zinc-100">{row.origen}</p>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400">→ {row.destino}</p>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            className="border-zinc-300 dark:border-zinc-600"
                            disabled={busy === String(row.id)}
                            aria-busy={busy === String(row.id)}
                            aria-label={p.downloadPdfAria.replace("{id}", String(row.id))}
                            onClick={async () => {
                              setErr(null);
                              setBusy(String(row.id));
                              try {
                                await portalDownloadFile(
                                  portalPorteCertificadoEsgUrl(row.id),
                                  `certificado-esg-${row.id}.pdf`,
                                );
                              } catch (e) {
                                setErr(e instanceof Error ? e.message : p.errCertPdf);
                              } finally {
                                setBusy(null);
                              }
                            }}
                          >
                            {p.downloadPdf}
                          </Button>
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
    </div>
  );
}
