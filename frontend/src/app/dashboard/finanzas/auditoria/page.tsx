"use client";

import { useState } from "react";
import Image from "next/image";
import { Copy, Download, Loader2, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, downloadAuditEvidencePackZip, type VerifactuChainAudit, type VerifactuQrPreview } from "@/lib/api";

export default function AuditoriaFiscalPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifactuChainAudit | null>(null);
  const [facturaIdInput, setFacturaIdInput] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState<VerifactuQrPreview | null>(null);
  const [urlCopied, setUrlCopied] = useState(false);
  const [packLoading, setPackLoading] = useState(false);

  const onVerify = async () => {
    setLoading(true);
    setError(null);
    try {
      const currentYear = new Date().getFullYear();
      const res = await api.verifactu.verifyChain(currentYear);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo verificar la cadena fiscal");
    } finally {
      setLoading(false);
    }
  };

  const onDownloadAuditPack = async () => {
    setPackLoading(true);
    setError(null);
    try {
      const blob = await downloadAuditEvidencePackZip();
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ab_logistics_os_audit_evidence_${stamp}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo descargar el paquete auditor");
    } finally {
      setPackLoading(false);
    }
  };

  const onPreviewQr = async () => {
    const idNum = Number(facturaIdInput);
    if (!Number.isFinite(idNum) || idNum <= 0) {
      setError("Introduce un ID de factura valido para previsualizar el QR.");
      return;
    }
    setPreviewLoading(true);
    setError(null);
    setUrlCopied(false);
    try {
      const res = await api.verifactu.getQrPreview(idNum);
      setPreview(res);
      if (!res.found) {
        setError("No se encontro la factura indicada para el tenant actual.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar la previsualizacion QR");
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <AppShell active="auditoria">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="p-8">
            <p className="text-sm text-zinc-600">
              Acceso restringido: la auditoría fiscal solo está disponible para owner.
            </p>
          </main>
        }
      >
        <main className="space-y-6 bg-zinc-950 p-8">
          <header>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
              <ShieldCheck className="h-6 w-6 text-emerald-500" aria-hidden />
              Auditoría de Integridad VeriFactu
            </h1>
            <p className="mt-1 text-sm text-zinc-400">
              Verificación criptográfica de encadenamiento fiscal.
            </p>
          </header>

          <Card className="bunker-card">
            <CardHeader>
              <CardTitle className="text-zinc-100">Paquete auditor (Due Diligence)</CardTitle>
              <CardDescription className="text-zinc-400">
                ZIP con compliance público, matriz de precios de catálogo y security.txt. Sin datos operativos ni PII
                de clientes. Ayuda: /help/audit-evidence-pack
              </CardDescription>
            </CardHeader>
            <CardContent>
              <button
                type="button"
                onClick={() => void onDownloadAuditPack()}
                disabled={packLoading}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-600/50 bg-emerald-950/30 px-4 py-2 text-sm font-medium text-emerald-200 hover:bg-emerald-900/40 disabled:opacity-60"
              >
                {packLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Descargar paquete auditor (ZIP)
              </button>
            </CardContent>
          </Card>

          <Card className="bunker-card">
            <CardHeader>
              <CardTitle className="text-zinc-100">Verificación de cadena fiscal</CardTitle>
              <CardDescription className="text-zinc-400">
                Comprueba que cada factura enlaza con el hash anterior sin alteraciones.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <button
                type="button"
                onClick={() => void onVerify()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-60"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Verificar Integridad Fiscal
              </button>

              {error && (
                <div className="rounded-md border border-rose-500/35 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
                  {error}
                </div>
              )}

              {result && (
                <div
                  className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
                    result.is_valid
                      ? "bg-emerald-950/50 text-emerald-400 ring-1 ring-emerald-500/30"
                      : "bg-rose-950/50 text-rose-300 ring-1 ring-rose-500/30"
                  }`}
                >
                  {result.is_valid
                    ? `Cadena Integra (${result.total_verified} verificadas)`
                    : `Inconsistencia en factura ${result.factura_id ?? "N/A"}`}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bunker-card">
            <CardHeader>
              <CardTitle className="text-zinc-100">Previsualización QR de factura</CardTitle>
              <CardDescription className="text-zinc-400">
                Comprueba que el QR codifica correctamente número, fecha, importe y huella fiscal.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  value={facturaIdInput}
                  onChange={(e) => setFacturaIdInput(e.target.value)}
                  placeholder="ID de factura"
                  className="w-48 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500"
                />
                <button
                  type="button"
                  onClick={() => void onPreviewQr()}
                  disabled={previewLoading}
                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-60"
                >
                  {previewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Previsualizar QR
                </button>
              </div>

              {preview?.found && preview.qr_png_base64 ? (
                <div className="rounded-lg border border-zinc-200 p-4 bg-white space-y-4">
                  <p className="text-sm text-zinc-700">
                    Factura {preview.numero_factura} · Hash:{" "}
                    <code className="text-xs">{preview.fingerprint_hash ?? "N/A"}</code>
                  </p>
                  <Image
                    src={`data:image/png;base64,${preview.qr_png_base64}`}
                    alt="QR VeriFactu"
                    width={176}
                    height={176}
                    className="h-44 w-44 rounded border border-zinc-200"
                    unoptimized
                  />
                  {preview.aeat_url ? (
                    <div>
                      <p className="text-xs font-medium text-zinc-500 mb-2">
                        URL de Cotejo Generada (Estándar SREI AEAT)
                      </p>
                      <div className="flex gap-2 rounded-lg border border-zinc-200 bg-zinc-100 p-3 dark:bg-zinc-800/60 dark:border-zinc-700">
                        <p className="min-w-0 flex-1 break-all font-mono text-[11px] leading-relaxed text-zinc-800 dark:text-zinc-200">
                          {preview.aeat_url}
                        </p>
                        <button
                          type="button"
                          onClick={() => {
                            void navigator.clipboard.writeText(preview.aeat_url ?? "").then(() => {
                              setUrlCopied(true);
                              window.setTimeout(() => setUrlCopied(false), 2000);
                            });
                          }}
                          className="shrink-0 inline-flex h-9 w-9 items-center justify-center rounded-md border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                          title="Copiar URL"
                          aria-label="Copiar URL de cotejo"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>
                      {urlCopied ? (
                        <p className="mt-1 text-xs text-emerald-500">Copiado al portapapeles</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </CardContent>
          </Card>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
