"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Award,
  Download,
  ExternalLink,
  FileJson,
  FileText,
  Leaf,
  Loader2,
  Lock,
  Shield,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  api,
  fetchAuditLogs,
  getAdvancedMetrics,
  type AuditLogRow,
  type FinanceEsgReport,
  type VerifactuChainAudit,
} from "@/lib/api";

function formatMonthYear(ym: string): string {
  const parts = ym.split("-");
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  if (!y || !m) return ym;
  const month = new Date(y, m - 1, 1).toLocaleDateString("es-ES", { month: "long" });
  const monthTitle = month.charAt(0).toUpperCase() + month.slice(1);
  return `${monthTitle} ${y}`;
}

/** Rango legible a partir de la serie mensual (p. ej. enero 2026 – abril 2026). */
function formatPeriodRangeFromSeries(meses: Array<{ periodo: string }>): string | null {
  if (meses.length === 0) return null;
  const sorted = [...meses].sort((a, b) => a.periodo.localeCompare(b.periodo));
  const first = sorted[0].periodo;
  const last = sorted[sorted.length - 1].periodo;
  if (first === last) return formatMonthYear(first);
  return `${formatMonthYear(first)} – ${formatMonthYear(last)}`;
}

function tablaOrigen(row: AuditLogRow): string {
  return (row.table_name || row.tabla_origen || "").trim();
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function describeAuditEvent(row: AuditLogRow): { tipo: string; descripcion: string } {
  const tn = (tablaOrigen(row) || "").toLowerCase();
  const act = (row.action || "").toUpperCase();
  const nd = row.new_data ?? {};
  const od = row.old_data ?? {};
  const blob = `${JSON.stringify(nd)} ${JSON.stringify(od)}`.toLowerCase();

  if (blob.includes("anonim") || blob.includes("pii") || blob.includes("encrypt"))
    return { tipo: "PII / anonimización", descripcion: `${tn} · ${act}` };
  if (tn.includes("export") || blob.includes("export") || act.includes("EXPORT"))
    return { tipo: "Exportación de datos", descripcion: `${tn} · ${act}` };
  if (act.includes("INVITE") || blob.includes("invite") || blob.includes("supabase_auth"))
    return { tipo: "Acceso / identidad", descripcion: `Evento de invitación o canal seguro · ${tn}` };
  if (tn === "facturas" || tn === "portes")
    return { tipo: "Integridad fiscal / operativa", descripcion: `${act} · ${tn}` };
  return { tipo: "Auditoría registrada", descripcion: `${tn} · ${act}` };
}

async function downloadJsonBlob(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadChainPdfReport(report: VerifactuChainAudit) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("Registro de encadenamiento VeriFactu (auditoría AEAT)", 14, 16);
  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(100, 116, 139);
  doc.text(
    "Documento generado a partir de la verificación criptográfica de huellas y eslabones previos.",
    14,
    22,
  );
  doc.setTextColor(0, 0, 0);
  const body = JSON.stringify(report, null, 2);
  const lines = doc.splitTextToSize(body, 182);
  let y = 30;
  const lineH = 3.6;
  doc.setFontSize(8);
  doc.setFont("courier", "normal");
  for (const line of lines) {
    if (y > 285) {
      doc.addPage();
      y = 14;
    }
    doc.text(line, 14, y);
    y += lineH;
  }
  const suffix = report.ejercicio != null ? String(report.ejercicio) : "completo";
  doc.save(`verifactu-encadenamiento-${suffix}.pdf`);
}

function CertificacionesContent() {
  const [chainReport, setChainReport] = useState<VerifactuChainAudit | null>(null);
  const [chainInitialLoading, setChainInitialLoading] = useState(true);
  const [jsonDownloading, setJsonDownloading] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [chainError, setChainError] = useState<string | null>(null);

  const [esgReport, setEsgReport] = useState<FinanceEsgReport | null>(null);
  const [esgReportLoading, setEsgReportLoading] = useState(true);
  const [esgError, setEsgError] = useState<string | null>(null);
  const [certDownloading, setCertDownloading] = useState(false);

  const [co2Rows, setCo2Rows] = useState<Array<{ periodo: string; co2: number }>>([]);

  const [auditRows, setAuditRows] = useState<AuditLogRow[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError] = useState<string | null>(null);

  const loadChain = useCallback(async () => {
    setChainInitialLoading(true);
    setChainError(null);
    try {
      const y = new Date().getFullYear();
      const res = await api.verifactu.verifyChain(y);
      setChainReport(res);
    } catch (e) {
      setChainError(e instanceof Error ? e.message : "No se pudo cargar el registro fiscal.");
      setChainReport(null);
    } finally {
      setChainInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadChain();
  }, [loadChain]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setAuditLoading(true);
      setAuditError(null);
      setEsgReportLoading(true);
      setEsgError(null);
      try {
        const [logs, metrics, esg] = await Promise.all([
          fetchAuditLogs(10),
          getAdvancedMetrics().catch(() => null),
          api.finance.fetchEsgReport().catch(() => null),
        ]);
        if (!cancelled) {
          setAuditRows(logs);
          if (metrics?.meses?.length) {
            setCo2Rows(
              metrics.meses.map((m) => ({
                periodo: m.periodo,
                co2: Math.max(0, m.emisiones_co2_kg ?? 0),
              })),
            );
          } else {
            setCo2Rows([]);
          }
          setEsgReport(esg);
        }
      } catch (e) {
        if (!cancelled) {
          setAuditError(e instanceof Error ? e.message : "No se pudo cargar el registro de auditoría.");
          setAuditRows([]);
        }
      } finally {
        if (!cancelled) {
          setAuditLoading(false);
          setEsgReportLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const chainDownloading = jsonDownloading || pdfDownloading;

  const onDownloadJson = useCallback(async () => {
    setJsonDownloading(true);
    setChainError(null);
    try {
      const y = new Date().getFullYear();
      const res = await api.verifactu.verifyChain(y);
      await downloadJsonBlob(res, `verifactu-encadenamiento-${y}.json`);
    } catch (e) {
      setChainError(e instanceof Error ? e.message : "Error al descargar JSON.");
    } finally {
      setJsonDownloading(false);
    }
  }, []);

  const onDownloadPdf = useCallback(async () => {
    setPdfDownloading(true);
    setChainError(null);
    try {
      const y = new Date().getFullYear();
      const res = await api.verifactu.verifyChain(y);
      await downloadChainPdfReport(res);
    } catch (e) {
      setChainError(e instanceof Error ? e.message : "Error al generar PDF.");
    } finally {
      setPdfDownloading(false);
    }
  }, []);

  const onDownloadEsgCert = useCallback(async () => {
    setCertDownloading(true);
    setEsgError(null);
    try {
      const blob = await api.finance.downloadEsgCertificatePdf();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `certificado_huella_carbono_${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setEsgError(e instanceof Error ? e.message : "No se pudo generar el certificado.");
    } finally {
      setCertDownloading(false);
    }
  }, []);

  const chartData = useMemo(() => {
    return co2Rows.map((r) => ({
      label: r.periodo.length >= 7 ? `${r.periodo.slice(5, 7)}/${r.periodo.slice(2, 4)}` : r.periodo,
      co2_kg: r.co2,
    }));
  }, [co2Rows]);

  const seriesPeriodLabel = useMemo(() => formatPeriodRangeFromSeries(co2Rows), [co2Rows]);

  const esgPeriodLabel = useMemo(() => {
    if (seriesPeriodLabel) return seriesPeriodLabel;
    if (esgReport?.periodo) return formatMonthYear(esgReport.periodo);
    return null;
  }, [seriesPeriodLabel, esgReport?.periodo]);

  return (
    <div className="mx-auto w-full max-w-6xl bg-zinc-950 p-6 md:p-10">
      <header className="mb-10 border-b border-zinc-800/90 pb-8">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Cumplimiento normativo</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold tracking-tight text-zinc-50 md:text-4xl">
          Certificaciones y cumplimiento
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
          Documentación oficial de integridad fiscal, huella de carbono y trazabilidad de eventos críticos para
          auditorías internas y externas.
        </p>
      </header>

      {chainError ? (
        <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-950/25 px-4 py-3 text-sm text-amber-100">
          {chainError}
        </div>
      ) : null}

      {/* Bento: dos tarjetas grandes */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-6">
        {/* Card 1 — VeriFactu */}
        <Card className="bunker-card relative overflow-hidden border-zinc-800/90">
          <div className="pointer-events-none absolute -right-8 -top-8 h-56 w-56 rounded-full bg-emerald-500/5 blur-3xl" />
          <CardHeader className="relative space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                <Shield className="h-4 w-4 text-emerald-500/90" aria-hidden />
                Blindaje fiscal
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className="inline-flex items-center justify-center rounded-full border-2 border-emerald-400/50 bg-emerald-950/60 px-6 py-3 text-center shadow-[0_0_40px_-12px_rgba(52,211,153,0.55)]">
                  <span className="text-[11px] font-bold uppercase tracking-[0.25em] text-emerald-300">
                    Sello garante
                  </span>
                </span>
                <span className="text-[10px] font-medium uppercase tracking-wide text-emerald-500/80">
                  VeriFactu · AEAT
                </span>
              </div>
            </div>
            <CardTitle className="font-serif text-xl text-zinc-50">Integridad de cadena y firma electrónica</CardTitle>
            <CardDescription className="text-sm leading-relaxed text-zinc-400">
              El 100% de las facturas emitidas en esta plataforma se sellan con firma electrónica avanzada (perfil
              equivalente a <strong className="font-medium text-zinc-300">XAdES-BES</strong>) y se encadenan
              criptográficamente para garantizar inalterabilidad ante la Agencia Tributaria.
            </CardDescription>
          </CardHeader>
          <CardContent className="relative space-y-5">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-3 text-xs text-zinc-500">
              {chainInitialLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-500" aria-hidden />
                  Comprobando cadena del ejercicio…
                </span>
              ) : chainReport ? (
                <span
                  className={
                    chainReport.is_valid
                      ? "font-medium text-emerald-400/95"
                      : "font-medium text-rose-300"
                  }
                >
                  {chainReport.is_valid
                    ? `Cadena verificada: ${chainReport.total_verified} factura(s) comprobadas en el ejercicio.`
                    : `Atención: posible incoherencia en factura ${chainReport.factura_id ?? "—"}.`}
                </span>
              ) : (
                <span>Sin datos de verificación todavía.</span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void onDownloadJson()}
                disabled={chainDownloading}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-2.5 text-sm font-medium text-zinc-100 transition-colors hover:border-emerald-500/40 hover:bg-zinc-800/40 disabled:opacity-50 min-[420px]:flex-none"
              >
                {jsonDownloading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-500" aria-hidden />
                ) : (
                  <FileJson className="h-4 w-4 text-emerald-500/90" aria-hidden />
                )}
                Registro JSON
              </button>
              <button
                type="button"
                onClick={() => void onDownloadPdf()}
                disabled={chainDownloading}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-2.5 text-sm font-medium text-zinc-100 transition-colors hover:border-emerald-500/40 hover:bg-zinc-800/40 disabled:opacity-50 min-[420px]:flex-none"
              >
                {pdfDownloading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-500" aria-hidden />
                ) : (
                  <FileText className="h-4 w-4 text-zinc-400" aria-hidden />
                )}
                Registro PDF
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-zinc-600">
              Los archivos incluyen el resultado de la verificación de encadenamiento para aportar a inspecciones
              AEAT y revisiones de terceros.
            </p>
          </CardContent>
        </Card>

        {/* Card 2 — ESG */}
        <Card className="bunker-card relative overflow-hidden border-zinc-800/90">
          <div className="pointer-events-none absolute -left-10 -bottom-10 h-48 w-48 rounded-full bg-emerald-500/5 blur-3xl" />
          <CardHeader className="relative space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              <Leaf className="h-4 w-4 text-emerald-500/90" aria-hidden />
              Reporte de sostenibilidad
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="font-serif text-xl text-zinc-50">Huella de carbono operativa</CardTitle>
              <span className="rounded-md border border-emerald-500/35 bg-emerald-950/40 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
                Framework GLEC compliant
              </span>
            </div>
            <CardDescription className="text-sm text-zinc-400">
              Metodología alineada con el cálculo de emisiones de transporte para reporting corporativo y clientes
              exigentes en <strong className="font-medium text-zinc-300">ESG</strong>.
            </CardDescription>
          </CardHeader>
          <CardContent className="relative space-y-5">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-3 text-sm">
              {esgReportLoading ? (
                <span className="inline-flex items-center gap-2 text-zinc-500">
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-500" aria-hidden />
                  Cargando reporte ESG…
                </span>
              ) : (
                <>
                  <p className="text-zinc-200">
                    <span className="font-medium text-zinc-500">Periodo:</span>{" "}
                    <span>{esgPeriodLabel ?? "—"}</span>
                  </p>
                  <p className="mt-2 text-base font-semibold tabular-nums text-zinc-50">
                    <span className="mr-2 text-sm font-normal text-zinc-500">Total CO₂ emitido</span>
                    {esgReport != null
                      ? `${esgReport.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg`
                      : "—"}
                  </p>
                  {esgReport ? (
                    <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">
                      Reporte oficial{" "}
                      <code className="rounded bg-zinc-900 px-1 py-0.5 text-zinc-400">GET /api/v1/finance/esg-report</code>
                      · Mes de referencia: {formatMonthYear(esgReport.periodo)} · {esgReport.total_portes} porte(s) en
                      periodo.
                    </p>
                  ) : (
                    <p className="mt-2 text-[11px] text-zinc-600">
                      No hay datos del reporte ESG para este tenant. El periodo mostrado arriba refleja la serie de
                      métricas cuando exista.
                    </p>
                  )}
                </>
              )}
            </div>
            <div className="h-[180px] w-full min-w-0">
              {chartData.length === 0 ? (
                <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-zinc-700">
                  <p className="text-sm text-zinc-500">Sin serie de CO₂ aún (métricas avanzadas).</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                    <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} tickFormatter={(v) => `${v}`} />
                    <Tooltip
                      cursor={{ fill: "rgba(39, 39, 42, 0.4)" }}
                      contentStyle={{
                        background: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(v) => [`${Number(v ?? 0).toLocaleString("es-ES", { maximumFractionDigits: 1 })} kg`, "CO₂"]}
                    />
                    <Bar dataKey="co2_kg" name="kg CO₂" fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-4 py-3 text-[11px] leading-relaxed text-zinc-500">
              <span className="font-semibold text-zinc-400">GLEC — nivel de precisión: </span>
              Nivel 3 (GLEC Accuracy Level 3): cálculo con{" "}
              <strong className="font-medium text-zinc-300">datos operativos reales</strong> por servicio (km, carga,
              vehículo / factor de emisión), no solo valores genéricos de sector.
            </div>
            {esgError ? (
              <div className="rounded-md border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-xs text-rose-200">
                {esgError}
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => void onDownloadEsgCert()}
              disabled={certDownloading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-emerald-500/35 bg-emerald-950/40 px-4 py-3 text-sm font-semibold text-emerald-100 transition-colors hover:bg-emerald-500/15 disabled:opacity-50"
            >
              {certDownloading ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Download className="h-4 w-4" aria-hidden />
              )}
              Generar certificado de huella de carbono (PDF)
            </button>
          </CardContent>
        </Card>
      </div>

      {/* Card 3 — Auditoría */}
      <section className="mt-8">
        <div className="mb-3 flex items-center gap-2">
          <Lock className="h-4 w-4 text-zinc-500" aria-hidden />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Registro de auditoría</h2>
        </div>
        <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/35">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-5 py-3">
            <span className="text-sm font-medium text-zinc-200">Últimos eventos críticos</span>
            <span className="text-xs text-zinc-500">Autenticación, exportaciones y datos personales</span>
          </div>
          <div className="w-full overflow-x-auto">
            {auditLoading ? (
              <div className="flex items-center justify-center gap-2 py-16 text-zinc-500">
                <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden />
                Cargando registro…
              </div>
            ) : auditError ? (
              <div className="px-5 py-10 text-center text-sm text-rose-300">{auditError}</div>
            ) : (
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                    <th className="px-5 py-3 font-semibold">Fecha / hora</th>
                    <th className="px-5 py-3 font-semibold">Tipo</th>
                    <th className="px-5 py-3 font-semibold">Descripción</th>
                    <th className="hidden px-5 py-3 font-semibold md:table-cell">Tabla origen</th>
                    <th className="px-5 py-3 text-right font-semibold">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  {auditRows.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-12 text-center text-zinc-500">
                        No hay entradas de auditoría recientes para este tenant.
                      </td>
                    </tr>
                  ) : (
                    auditRows.map((row) => {
                      const { tipo, descripcion } = describeAuditEvent(row);
                      const origen = tablaOrigen(row);
                      const isPorte = origen === "portes";
                      return (
                        <tr key={row.id} className="transition-colors hover:bg-zinc-800/25">
                          <td className="whitespace-nowrap px-5 py-3 text-zinc-400">
                            {formatDateTime(row.created_at)}
                          </td>
                          <td className="px-5 py-3">
                            <span className="rounded-md border border-zinc-700 bg-zinc-950/60 px-2 py-0.5 text-xs text-zinc-300">
                              {tipo}
                            </span>
                          </td>
                          <td className="max-w-md px-5 py-3 text-zinc-300">{descripcion}</td>
                          <td className="hidden px-5 py-3 font-mono text-xs text-zinc-500 md:table-cell">
                            {origen || "—"}
                          </td>
                          <td className="px-5 py-3 text-right">
                            {isPorte ? (
                              <Link
                                href={`/dashboard/portes/${encodeURIComponent(row.record_id)}`}
                                className="inline-flex items-center justify-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-2.5 py-1.5 text-xs font-medium text-emerald-300 transition-colors hover:border-emerald-500/50 hover:bg-emerald-950/50"
                              >
                                Ver detalle
                                <ExternalLink className="h-3.5 w-3.5 opacity-80" aria-hidden />
                              </Link>
                            ) : (
                              <span className="text-zinc-600">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>

      <footer className="mt-12 flex flex-wrap items-center gap-2 border-t border-zinc-800/80 pt-6 text-[11px] text-zinc-600">
        <Award className="h-3.5 w-3.5 shrink-0 text-zinc-600" aria-hidden />
        <span>
          AB Logistics OS — documentación orientada a cumplimiento; conserve estos registros junto con su política de
          seguridad de la información.
        </span>
      </footer>
    </div>
  );
}

export default function CertificacionesPage() {
  return (
    <AppShell active="certificaciones">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-500">Esta área está reservada a administradores de la empresa.</p>
          </main>
        }
      >
        <CertificacionesContent />
      </RoleGuard>
    </AppShell>
  );
}
