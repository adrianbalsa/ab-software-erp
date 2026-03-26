"use client";

import { useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type VerifactuChainAudit, type VerifactuQrPreview } from "@/lib/api";

export default function AuditoriaFiscalPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifactuChainAudit | null>(null);
  const [facturaIdInput, setFacturaIdInput] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState<VerifactuQrPreview | null>(null);

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

  const onPreviewQr = async () => {
    const idNum = Number(facturaIdInput);
    if (!Number.isFinite(idNum) || idNum <= 0) {
      setError("Introduce un ID de factura valido para previsualizar el QR.");
      return;
    }
    setPreviewLoading(true);
    setError(null);
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
    <AppShell active="finanzas">
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
        <main className="p-8 space-y-6">
          <header>
            <h1 className="text-2xl font-bold text-zinc-900 flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-blue-600" />
              Auditoría de Integridad VeriFactu
            </h1>
            <p className="text-sm text-zinc-500 mt-1">
              Verificación criptográfica de encadenamiento fiscal.
            </p>
          </header>

          <Card>
            <CardHeader>
              <CardTitle>Verificación de cadena fiscal</CardTitle>
              <CardDescription>
                Comprueba que cada factura enlaza con el hash anterior sin alteraciones.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <button
                type="button"
                onClick={() => void onVerify()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Verificar Integridad Fiscal
              </button>

              {error && (
                <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}

              {result && (
                <div
                  className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
                    result.is_valid
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-rose-100 text-rose-800"
                  }`}
                >
                  {result.is_valid
                    ? `Cadena Integra (${result.total_verified} verificadas)`
                    : `Inconsistencia en factura ${result.factura_id ?? "N/A"}`}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Previsualización QR de factura</CardTitle>
              <CardDescription>
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
                  className="w-48 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={() => void onPreviewQr()}
                  disabled={previewLoading}
                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
                >
                  {previewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Previsualizar QR
                </button>
              </div>

              {preview?.found && preview.qr_png_base64 ? (
                <div className="rounded-lg border border-zinc-200 p-4 bg-white">
                  <p className="text-sm text-zinc-700 mb-2">
                    Factura {preview.numero_factura} · Hash:{" "}
                    <code className="text-xs">{preview.fingerprint_hash ?? "N/A"}</code>
                  </p>
                  <img
                    src={`data:image/png;base64,${preview.qr_png_base64}`}
                    alt="QR VeriFactu"
                    className="w-44 h-44 border border-zinc-200 rounded"
                  />
                </div>
              ) : null}
            </CardContent>
          </Card>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
