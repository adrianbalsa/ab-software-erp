"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Download, FileText, RefreshCw, FileWarning, Stamp } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { VeriFactuBadge } from "@/components/dashboard/VeriFactuBadge";
import { SendInvoiceButton } from "@/components/facturas/SendInvoiceButton";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { API_BASE, api, apiFetch, type Factura } from "@/lib/api";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { formatCurrencyEUR } from "@/i18n/localeFormat";

function puedeReenviarAeat(r: Factura): boolean {
  if (!r.is_finalized || !r.fingerprint) return false;
  const e = (r.aeat_sif_estado ?? "").toLowerCase();
  return e === "error_tecnico" || e === "rechazado" || e === "omitido" || e === "aceptado_con_errores";
}

export default function FacturasPage() {
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages;

  const [rows, setRows] = useState<Factura[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastPayload | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [rectTarget, setRectTarget] = useState<Factura | null>(null);
  const [motivo, setMotivo] = useState("");
  const [rectBusy, setRectBusy] = useState(false);
  const [rectError, setRectError] = useState<string | null>(null);
  const [aeatBusyId, setAeatBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.facturas.getAll());
    } catch {
      setRows([]);
      setToast({
        id: Date.now(),
        tone: "error",
        message: p.facturas.loadError,
      });
    } finally {
      setLoading(false);
    }
  }, [p.facturas.loadError]);

  useEffect(() => {
    void load();
  }, [load]);

  const openRectificar = (r: Factura) => {
    setRectTarget(r);
    setMotivo("");
    setRectError(null);
    setModalOpen(true);
  };

  const closeModal = () => {
    if (rectBusy) return;
    setModalOpen(false);
    setRectTarget(null);
    setMotivo("");
    setRectError(null);
  };

  const enviarRectificativa = async () => {
    if (!rectTarget) return;
    const m = motivo.trim();
    if (m.length < 3) {
      setRectError(p.facturas.motivoShort);
      return;
    }
    setRectBusy(true);
    setRectError(null);
    try {
      const res = await apiFetch(`${API_BASE}/facturas/${rectTarget.id}/rectificar`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ motivo: m }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const d = err?.detail;
        throw new Error(typeof d === "string" ? d : `HTTP ${res.status}`);
      }
      closeModal();
      await load();
    } catch (e: unknown) {
      setRectError(e instanceof Error ? e.message : p.facturas.rectError);
    } finally {
      setRectBusy(false);
    }
  };

  const reenviarAeat = async (r: Factura) => {
    const idStr = String(r.id);
    setAeatBusyId(idStr);
    try {
      const res = await apiFetch(`${API_BASE}/facturas/${idStr}/reenviar-aeat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const d = err?.detail;
        throw new Error(typeof d === "string" ? d : `HTTP ${res.status}`);
      }
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : p.facturas.aeatFail);
    } finally {
      setAeatBusyId(null);
    }
  };

  const descargarPdfInmutable = async (id: string) => {
    setDownloadingId(id);
    try {
      const res = await apiFetch(`${API_BASE}/reports/facturas/${id}/pdf`, {
        credentials: "include",
        headers: { Accept: "application/pdf" },
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t.slice(0, 120) || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `factura_${id.slice(0, 8)}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : p.facturas.pdfFail);
    } finally {
      setDownloadingId(null);
    }
  };

  const copyAeatCsv = useCallback(async (csv: string) => {
    try {
      await navigator.clipboard.writeText(csv);
      setToast({ id: Date.now(), tone: "success", message: p.facturas.csvCopied });
    } catch {
      setToast({ id: Date.now(), tone: "error", message: p.facturas.csvFail });
    }
  }, [p.facturas.csvCopied, p.facturas.csvFail]);

  return (
    <AppShell active="facturas">
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={3200} />
      <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">{p.facturas.title}</h1>
          <p className="text-sm text-slate-500">{p.facturas.subtitle}</p>
          <Link
            href="/help/erp-invoicing"
            className="mt-1 inline-block text-xs font-medium text-[#2563eb] underline-offset-2 hover:underline"
          >
            {p.facturas.helpErpInvoices}
          </Link>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {p.facturas.refresh}
        </button>
      </header>

      <main className="p-8 flex-1 overflow-y-auto">
        <div className="ab-card rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2 bg-slate-50/80">
            <FileText className="w-5 h-5 text-[#2563eb]" />
            <h2 className="font-bold text-[#0b1224]">{p.facturas.issued}</h2>
          </div>
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="ab-table w-full min-w-[800px]">
              <thead>
                <tr>
                  <th>{p.facturas.colNumber}</th>
                  <th>{p.facturas.colType}</th>
                  <th>{p.facturas.colDate}</th>
                  <th>{p.facturas.colTotal}</th>
                  <th>{p.facturas.colAeat}</th>
                  <th>{p.facturas.colHash}</th>
                  <th className="text-right">{p.facturas.colActions}</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-slate-500 text-sm py-8 text-center">
                      {p.facturas.loading}
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-slate-500 text-sm py-8 text-center">
                      {p.facturas.empty}
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={String(r.id)}>
                      <td className="font-medium text-slate-800">
                        <Link
                          href={`/facturas/${String(r.id)}`}
                          className="text-[#2563eb] hover:underline"
                        >
                          {r.numero_factura}
                        </Link>
                      </td>
                      <td className="text-slate-600 text-sm">{r.tipo_factura ?? "—"}</td>
                      <td className="text-slate-600">{String(r.fecha_emision).slice(0, 10)}</td>
                      <td className="text-slate-800">
                        {formatCurrencyEUR(Number(r.total_factura), locale)}
                      </td>
                      <td className="text-left align-middle">
                        <div className="inline-flex items-center gap-2">
                          <VeriFactuBadge
                            estado={r.aeat_sif_estado}
                            descripcion={r.aeat_sif_descripcion}
                          />
                          {r.aeat_sif_csv && (
                            <button
                              type="button"
                              onClick={() => void copyAeatCsv(r.aeat_sif_csv || "")}
                              className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-100"
                              title={p.facturas.copyCsvTitle}
                              aria-label={p.facturas.copyCsvAria}
                            >
                              <Stamp className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="font-mono text-xs text-slate-500 max-w-[200px] truncate">
                        {r.hash_registro ? `${r.hash_registro.slice(0, 14)}…` : "—"}
                      </td>
                      <td className="text-right">
                        <div className="inline-flex flex-wrap items-center justify-end gap-2">
                          {puedeReenviarAeat(r) && (
                            <button
                              type="button"
                              disabled={aeatBusyId === String(r.id)}
                              onClick={() => void reenviarAeat(r)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${aeatBusyId === String(r.id) ? "animate-spin" : ""}`} />
                              {p.facturas.reenviarAeat}
                            </button>
                          )}
                          {r.tipo_factura === "F1" && (
                            <button
                              type="button"
                              onClick={() => openRectificar(r)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                            >
                              <FileWarning className="w-3.5 h-3.5" />
                              {p.facturas.rectificar}
                            </button>
                          )}
                          <SendInvoiceButton
                            facturaId={r.id}
                            onToast={(message, tone) =>
                              setToast({ id: Date.now(), message, tone })
                            }
                          />
                          <button
                            type="button"
                            disabled={downloadingId === String(r.id)}
                            onClick={() => void descargarPdfInmutable(String(r.id))}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#2563eb] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1d4ed8] disabled:opacity-50"
                          >
                            <Download className="w-3.5 h-3.5" />
                            {downloadingId === String(r.id) ? "…" : p.facturas.pdf}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {modalOpen && rectTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="rect-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl border border-slate-200">
            <div className="border-b border-slate-100 px-6 py-4">
              <h3 id="rect-modal-title" className="text-lg font-bold text-slate-900">
                {p.facturas.modalTitle} {rectTarget.numero_factura}
              </h3>
              <p className="text-sm text-slate-500 mt-1">{p.facturas.modalIntro}</p>
            </div>
            <div className="px-6 py-4 space-y-3">
              <label className="block text-sm font-semibold text-slate-700" htmlFor="motivo-rect">
                {p.facturas.motivoLabel}
              </label>
              <textarea
                id="motivo-rect"
                rows={4}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
                placeholder={p.facturas.motivoPlaceholder}
                disabled={rectBusy}
              />
              {rectError && (
                <p className="text-sm text-red-600" role="alert">
                  {rectError}
                </p>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4 bg-slate-50/80 rounded-b-2xl">
              <button
                type="button"
                onClick={closeModal}
                disabled={rectBusy}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-50"
              >
                {p.facturas.cancel}
              </button>
              <button
                type="button"
                onClick={() => void enviarRectificativa()}
                disabled={rectBusy}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {rectBusy ? p.facturas.emitting : p.facturas.emitR1}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
