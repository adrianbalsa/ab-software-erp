"use client";

import { useCallback, useEffect, useState } from "react";
import { FileText } from "lucide-react";

import {
  apiFetch,
  fetchPortalFacturas,
  parseApiError,
  portalFacturaPdfUrl,
  postPortalSetupMandate,
  refreshAccessToken,
  type PortalFacturaRow,
} from "@/lib/api";
import { SetupMandateCard } from "@/components/portal/SetupMandateCard";

function fmtMoney(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function PortalFacturasPage() {
  const [rows, setRows] = useState<PortalFacturaRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<number | null>(null);
  const [isSettingUpMandate, setIsSettingUpMandate] = useState(false);
  const [hasActiveMandate, setHasActiveMandate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await fetchPortalFacturas());
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudieron cargar las facturas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSetupMandate = useCallback(async () => {
    if (isSettingUpMandate) return;
    setIsSettingUpMandate(true);
    setError(null);
    try {
      const out = await postPortalSetupMandate();
      if (out.has_active_mandate) setHasActiveMandate(true);
      if (!out.redirect_url || !out.redirect_url.trim()) {
        throw new Error("No se recibió URL de redirección para GoCardless.");
      }
      window.location.href = out.redirect_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo iniciar la domiciliación.");
      setIsSettingUpMandate(false);
    }
  }, [isSettingUpMandate]);

  return (
    <div className="mx-auto max-w-5xl px-4 pb-12 pt-8 sm:px-6">
      <SetupMandateCard
        hasActiveMandate={hasActiveMandate}
        isLoading={isSettingUpMandate}
        onSetup={handleSetupMandate}
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <section className="rounded-2xl border border-zinc-200/90 bg-white shadow-sm">
        <div className="border-b border-zinc-100 px-5 py-4">
          <h2 className="text-base font-semibold text-zinc-900">Mis facturas</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-100 bg-zinc-50/80 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <th className="px-5 py-3">Número</th>
                <th className="px-5 py-3">Fecha</th>
                <th className="px-5 py-3">Importe</th>
                <th className="px-5 py-3">Estado</th>
                <th className="px-5 py-3 text-right">PDF</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-zinc-500">
                    Cargando…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-zinc-500">
                    No hay facturas emitidas aún.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="border-b border-zinc-50 last:border-0 hover:bg-zinc-50/50">
                    <td className="px-5 py-3.5 font-mono text-sm font-medium text-zinc-900">{row.numero_factura}</td>
                    <td className="px-5 py-3.5 text-zinc-600">{row.fecha_emision?.slice(0, 10) ?? "—"}</td>
                    <td className="px-5 py-3.5 text-zinc-800">{fmtMoney(row.total_factura)}</td>
                    <td className="px-5 py-3.5">{row.estado_pago}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        type="button"
                        disabled={downloading === row.id}
                        onClick={async () => {
                          setDownloading(row.id);
                          try {
                            async function doFetch(): Promise<Response> {
                              return apiFetch(portalFacturaPdfUrl(row.id), {
                                credentials: "include",
                              });
                            }
                            let res = await doFetch();
                            if (res.status === 401) {
                              const t = await refreshAccessToken();
                              if (t) res = await doFetch();
                            }
                            if (!res.ok) throw new Error(await parseApiError(res));
                            const blob = await res.blob();
                            const u = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = u;
                            a.download = `factura-${row.id}.pdf`;
                            a.click();
                            URL.revokeObjectURL(u);
                          } catch (e) {
                            setError(e instanceof Error ? e.message : "Error al descargar factura.");
                          } finally {
                            setDownloading(null);
                          }
                        }}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-800 shadow-sm transition hover:bg-zinc-50 disabled:opacity-60"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        {downloading === row.id ? "Descargando…" : "Descargar factura"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

