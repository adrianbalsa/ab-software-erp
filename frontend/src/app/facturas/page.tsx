"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Download, FileText, RefreshCw, FileWarning, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { API_BASE, authHeaders } from "@/lib/api";

type FacturaRow = {
  id: string;
  numero_factura: string;
  fecha_emision: string;
  total_factura: number;
  hash_registro?: string | null;
  tipo_factura?: string | null;
  is_finalized?: boolean | null;
  fingerprint?: string | null;
  aeat_sif_estado?: string | null;
};

function aeatEstadoBadge(estado: string | null | undefined): { label: string; className: string } {
  const e = (estado ?? "").toLowerCase();
  if (e === "aceptado" || e === "enviado_ok") {
    return {
      label: "AEAT: enviado",
      className: "border border-emerald-200 bg-emerald-50 text-emerald-900",
    };
  }
  if (e === "rechazado" || e === "error_tecnico") {
    return {
      label: "AEAT: error",
      className: "border border-red-200 bg-red-50 text-red-900",
    };
  }
  if (e === "omitido") {
    return {
      label: "AEAT: sin URL/cert",
      className: "border border-amber-200 bg-amber-50 text-amber-950",
    };
  }
  if (e === "aceptado_con_errores") {
    return {
      label: "AEAT: avisos",
      className: "border border-amber-200 bg-amber-50 text-amber-950",
    };
  }
  return {
    label: "AEAT: pendiente",
    className: "border border-amber-200 bg-amber-50 text-amber-950",
  };
}

function puedeReenviarAeat(r: FacturaRow): boolean {
  if (!r.is_finalized || !r.fingerprint) return false;
  const e = (r.aeat_sif_estado ?? "").toLowerCase();
  return e === "error_tecnico" || e === "rechazado" || e === "omitido" || e === "aceptado_con_errores";
}

export default function FacturasPage() {
  const [rows, setRows] = useState<FacturaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [rectTarget, setRectTarget] = useState<FacturaRow | null>(null);
  const [motivo, setMotivo] = useState("");
  const [rectBusy, setRectBusy] = useState(false);
  const [rectError, setRectError] = useState<string | null>(null);
  const [aeatBusyId, setAeatBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/facturas/`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      const json = (await res.json()) as FacturaRow[];
      setRows(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openRectificar = (r: FacturaRow) => {
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
      setRectError("Indica un motivo (mín. 3 caracteres).");
      return;
    }
    setRectBusy(true);
    setRectError(null);
    try {
      const res = await fetch(`${API_BASE}/facturas/${rectTarget.id}/rectificar`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...authHeaders(),
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
      setRectError(e instanceof Error ? e.message : "Error al rectificar");
    } finally {
      setRectBusy(false);
    }
  };

  const reenviarAeat = async (r: FacturaRow) => {
    setAeatBusyId(r.id);
    try {
      const res = await fetch(`${API_BASE}/facturas/${r.id}/reenviar-aeat`, {
        method: "POST",
        credentials: "include",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const d = err?.detail;
        throw new Error(typeof d === "string" ? d : `HTTP ${res.status}`);
      }
      await load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "No se pudo reenviar a la AEAT");
    } finally {
      setAeatBusyId(null);
    }
  };

  const descargarPdfInmutable = async (id: string) => {
    setDownloadingId(id);
    try {
      const res = await fetch(`${API_BASE}/reports/facturas/${id}/pdf`, {
        credentials: "include",
        headers: { ...authHeaders(), Accept: "application/pdf" },
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
      alert(e instanceof Error ? e.message : "No se pudo descargar el PDF");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <AppShell active="facturas">
      <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Facturas</h1>
          <p className="text-sm text-slate-500">
            PDF inmutable vía <code className="text-xs">porte_lineas_snapshot</code> + VeriFactu · Rectificativas R1
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </header>

      <main className="p-8 flex-1 overflow-y-auto">
        {error && (
          <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {error}
          </div>
        )}

        <div className="ab-card rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2 bg-slate-50/80">
            <FileText className="w-5 h-5 text-[#2563eb]" />
            <h2 className="font-bold text-[#0b1224]">Facturas emitidas</h2>
          </div>
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="ab-table w-full min-w-[800px]">
              <thead>
                <tr>
                  <th>Número</th>
                  <th>Tipo</th>
                  <th>Fecha</th>
                  <th>Total</th>
                  <th>Estado AEAT</th>
                  <th>Hash (preview)</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-slate-500 text-sm py-8 text-center">
                      Cargando…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-slate-500 text-sm py-8 text-center">
                      No hay facturas.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.id}>
                      <td className="font-medium text-slate-800">
                        <Link
                          href={`/facturas/${r.id}`}
                          className="text-[#2563eb] hover:underline"
                        >
                          {r.numero_factura}
                        </Link>
                      </td>
                      <td className="text-slate-600 text-sm">{r.tipo_factura ?? "—"}</td>
                      <td className="text-slate-600">{String(r.fecha_emision).slice(0, 10)}</td>
                      <td className="text-slate-800">
                        {Number(r.total_factura).toLocaleString("es-ES", {
                          style: "currency",
                          currency: "EUR",
                        })}
                      </td>
                      <td className="text-left align-middle">
                        <span
                          className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold ${aeatEstadoBadge(r.aeat_sif_estado).className}`}
                          title={r.aeat_sif_estado ?? "pendiente"}
                        >
                          <ShieldCheck className="w-3 h-3 shrink-0 opacity-80" />
                          {aeatEstadoBadge(r.aeat_sif_estado).label}
                        </span>
                      </td>
                      <td className="font-mono text-xs text-slate-500 max-w-[200px] truncate">
                        {r.hash_registro ? `${r.hash_registro.slice(0, 14)}…` : "—"}
                      </td>
                      <td className="text-right">
                        <div className="inline-flex flex-wrap items-center justify-end gap-2">
                          {puedeReenviarAeat(r) && (
                            <button
                              type="button"
                              disabled={aeatBusyId === r.id}
                              onClick={() => void reenviarAeat(r)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${aeatBusyId === r.id ? "animate-spin" : ""}`} />
                              Reenviar AEAT
                            </button>
                          )}
                          {r.tipo_factura === "F1" && (
                            <button
                              type="button"
                              onClick={() => openRectificar(r)}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                            >
                              <FileWarning className="w-3.5 h-3.5" />
                              Rectificar
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={downloadingId === r.id}
                            onClick={() => void descargarPdfInmutable(r.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#2563eb] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1d4ed8] disabled:opacity-50"
                          >
                            <Download className="w-3.5 h-3.5" />
                            {downloadingId === r.id ? "…" : "PDF"}
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
                Rectificar factura {rectTarget.numero_factura}
              </h3>
              <p className="text-sm text-slate-500 mt-1">
                Se emitirá una factura <strong>R1</strong> con importes negativos vinculada a esta F1.
              </p>
            </div>
            <div className="px-6 py-4 space-y-3">
              <label className="block text-sm font-semibold text-slate-700" htmlFor="motivo-rect">
                Motivo de la rectificación
              </label>
              <textarea
                id="motivo-rect"
                rows={4}
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#2563eb]/30"
                placeholder="Ej.: Error en datos fiscales del cliente…"
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
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void enviarRectificativa()}
                disabled={rectBusy}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {rectBusy ? "Emitiendo…" : "Emitir R1"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
