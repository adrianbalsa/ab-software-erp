"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { pdf } from "@react-pdf/renderer";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { FacturaDocument, type FacturaPdfPayload } from "@/components/facturas/FacturaPdfTemplate";
import { InvoiceQR } from "@/components/facturas/InvoiceQR";
import { getFacturaPdfData, type FacturaPdfData } from "@/lib/api";

function slugFilePart(raw: string, max = 48): string {
  const t = (raw || "Cliente").trim();
  const s = t.replace(/[^\w\u00C0-\u024f-]+/gi, "_").replace(/_+/g, "_");
  return (s || "Cliente").slice(0, max);
}

export default function FacturaDetallePage() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [data, setData] = useState<FacturaPdfData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const d = await getFacturaPdfData(id);
      setData(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const descargarVerifactu = async () => {
    if (!data) return;
    setDownloading(true);
    try {
      const payload = data as FacturaPdfPayload;
      const blob = await pdf(<FacturaDocument data={payload} />).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Factura_${slugFilePart(data.numero_factura)}_${slugFilePart(data.receptor.nombre)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "No se pudo generar el PDF");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <AppShell active="facturas">
      <header className="h-16 ab-header flex shrink-0 items-center justify-between border-b border-slate-200/80 px-8">
        <div className="flex items-center gap-4">
          <Link
            href="/facturas"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-[#2563eb]"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver
          </Link>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-800">Detalle de factura</h1>
            {data && (
              <p className="text-sm text-slate-500">
                {data.num_factura_verifactu || data.numero_factura} ·{" "}
                {String(data.fecha_emision).slice(0, 10)}
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          disabled={!data || downloading}
          onClick={() => void descargarVerifactu()}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-[#2563eb] px-5 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-[#1d4ed8] disabled:opacity-50"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Descargar PDF (VeriFactu)
        </button>
      </header>

      <main className="flex-1 overflow-y-auto p-8">
        {loading && (
          <div className="flex items-center gap-2 text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" />
            Cargando datos…
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        )}
        {data && !loading && (
          <div className="mx-auto max-w-3xl space-y-6">
            <div className="ab-card rounded-2xl border border-slate-100 p-6">
              <h2 className="mb-4 text-sm font-bold uppercase tracking-wide text-slate-500">Emisor y cliente</h2>
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold text-slate-400">Emisor</p>
                  <p className="font-semibold text-slate-900">{data.emisor.nombre}</p>
                  <p className="text-sm text-slate-600">NIF {data.emisor.nif || "—"}</p>
                  {data.emisor.direccion && <p className="text-sm text-slate-600">{data.emisor.direccion}</p>}
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-400">Cliente</p>
                  <p className="font-semibold text-slate-900">{data.receptor.nombre}</p>
                  <p className="text-sm text-slate-600">NIF {data.receptor.nif || "—"}</p>
                </div>
              </div>
            </div>

            <div className="ab-card rounded-2xl border border-slate-100 p-6">
              <h2 className="mb-4 text-sm font-bold uppercase tracking-wide text-slate-500">Conceptos</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase text-slate-500">
                      <th className="py-2 pr-4">Concepto</th>
                      <th className="py-2 pr-4 text-right">Cant.</th>
                      <th className="py-2 pr-4 text-right">Precio</th>
                      <th className="py-2 text-right">Importe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.lineas.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-4 text-slate-500">
                          Sin líneas en snapshot.
                        </td>
                      </tr>
                    ) : (
                      data.lineas.map((ln, i) => (
                        <tr key={i} className="border-b border-slate-100">
                          <td className="py-2 pr-4 text-slate-800">{ln.concepto}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">{ln.cantidad}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">
                            {ln.precio_unitario.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                          </td>
                          <td className="py-2 text-right tabular-nums font-medium">
                            {ln.importe.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 flex flex-col items-end gap-1 border-t border-slate-100 pt-4 text-sm">
                <div className="flex w-full max-w-xs justify-between text-slate-600">
                  <span>Base imponible</span>
                  <span className="tabular-nums">
                    {data.base_imponible.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                  </span>
                </div>
                <div className="flex w-full max-w-xs justify-between text-slate-600">
                  <span>IVA ({data.tipo_iva_porcentaje.toFixed(2)}%)</span>
                  <span className="tabular-nums">
                    {data.cuota_iva.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                  </span>
                </div>
                <div className="flex w-full max-w-xs justify-between border-t border-slate-200 pt-2 text-base font-bold text-slate-900">
                  <span>Total</span>
                  <span className="tabular-nums">
                    {data.total_factura.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
                  </span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-6">
              <h2 className="mb-4 text-sm font-bold text-emerald-900">VeriFactu</h2>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <InvoiceQR url={data.verifactu_validation_url} size={120} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-emerald-900/90">
                    Huella (auditoría):{" "}
                    <code className="rounded bg-white/80 px-1.5 py-0.5 font-mono text-xs">
                      {data.verifactu_hash_audit || "—"}
                    </code>
                  </p>
                  <p className="mt-2 text-xs text-emerald-800/80">
                    Misma URL que el QR del PDF (consulta pública AEAT / VeriFactu). Escanee para
                    comprobar el registro.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </AppShell>
  );
}
