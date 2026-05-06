"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { RoleGuard } from "@/components/auth/RoleGuard";
import {
  API_BASE,
  apiFetch,
  downloadEsgIso14083Export,
  fetchEsgCertificateRegistry,
  jwtRbacRole,
  parseApiError,
  postEsgCertificateExternallyVerify,
  type AppRbacRole,
  type EsgCertificateRegistryRow,
} from "@/lib/api";
import { userFacingFetchFailureMessage } from "@/lib/api-base";

type ESGAuditClienteItem = {
  cliente_id: string;
  cliente_nombre: string | null;
  co2_kg: number;
};

type ESGAuditCertificacionPie = {
  certificacion: "Euro V" | "Euro VI" | "Electrico" | "Hibrido";
  co2_kg: number;
  porcentaje: number;
};

type ESGAuditOut = {
  fecha_inicio: string;
  fecha_fin: string;
  total_huella_carbono_kg: number;
  top_clientes: ESGAuditClienteItem[];
  porcentaje_emisiones_euro_v: number;
  porcentaje_emisiones_euro_vi: number;
  desglose_certificacion: ESGAuditCertificacionPie[];
  insight_optimizacion: string;
  escenario_optimizacion_pct: number;
  co2_ahorro_escenario_kg: number;
};

const PIE_COLORS: Record<string, string> = {
  "Euro V": "#f97316",
  "Euro VI": "#22c55e",
  Electrico: "#38bdf8",
  Hibrido: "#a78bfa",
};

const ALLOWED: AppRbacRole[] = ["owner", "traffic_manager"];

function defaultDateRange() {
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth(), 1);
  return {
    inicio: start.toISOString().slice(0, 10),
    fin: end.toISOString().slice(0, 10),
  };
}

export default function EsgAuditoriaPage() {
  const { inicio: defaultInicio, fin: defaultFin } = useMemo(() => defaultDateRange(), []);
  const [fechaInicio, setFechaInicio] = useState(defaultInicio);
  const [fechaFin, setFechaFin] = useState(defaultFin);
  const [data, setData] = useState<ESGAuditOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [certOpen, setCertOpen] = useState(false);
  const [registry, setRegistry] = useState<EsgCertificateRegistryRow[]>([]);
  const [registryLoading, setRegistryLoading] = useState(false);
  const [registryErr, setRegistryErr] = useState<string | null>(null);
  const [flowErr, setFlowErr] = useState<string | null>(null);
  const [verifyCode, setVerifyCode] = useState("");
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState<"csv" | "json" | "json_auditor" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams();
      q.set("fecha_inicio", fechaInicio);
      q.set("fecha_fin", fechaFin);
      const res = await apiFetch(`${API_BASE}/api/v1/esg/audit-report?${q.toString()}`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res));
      }
      const j = (await res.json()) as ESGAuditOut;
      setData(j);
    } catch (e: unknown) {
      setData(null);
      setError(userFacingFetchFailureMessage(e));
    } finally {
      setLoading(false);
    }
  }, [fechaInicio, fechaFin]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadRegistry = useCallback(async () => {
    setRegistryLoading(true);
    setRegistryErr(null);
    try {
      const rows = await fetchEsgCertificateRegistry(80);
      setRegistry(rows);
    } catch (e: unknown) {
      setRegistry([]);
      setRegistryErr(userFacingFetchFailureMessage(e));
    } finally {
      setRegistryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRegistry();
  }, [loadRegistry]);

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onExportIso = async (formato: "csv" | "json", forExternalAuditor: boolean) => {
    const key = formato === "json" && forExternalAuditor ? "json_auditor" : formato;
    setExportBusy(key);
    setFlowErr(null);
    try {
      const blob = await downloadEsgIso14083Export({
        fechaInicio: fechaInicio,
        fechaFin: fechaFin,
        formato,
        forExternalAuditor,
      });
      const ext = formato === "json" ? "json" : "csv";
      const tag = forExternalAuditor ? "_auditor_safe" : "";
      downloadBlob(blob, `esg_iso14083_export_${fechaInicio}_${fechaFin}${tag}.${ext}`);
    } catch (e: unknown) {
      setFlowErr(userFacingFetchFailureMessage(e));
    } finally {
      setExportBusy(null);
    }
  };

  const onVerifyExternal = async () => {
    const code = verifyCode.trim();
    if (code.length < 8) {
      setVerifyMsg("Introduce el código UUID completo del certificado.");
      return;
    }
    setVerifyLoading(true);
    setVerifyMsg(null);
    try {
      await postEsgCertificateExternallyVerify(code);
      setVerifyMsg("Estado actualizado a externally_verified.");
      setVerifyCode("");
      await loadRegistry();
    } catch (e: unknown) {
      setVerifyMsg(userFacingFetchFailureMessage(e));
    } finally {
      setVerifyLoading(false);
    }
  };

  const pieData = useMemo(() => {
    if (!data?.desglose_certificacion?.length) return [];
    return data.desglose_certificacion.map((d) => ({
      name: d.certificacion,
      value: d.porcentaje,
      co2_kg: d.co2_kg,
    }));
  }, [data]);

  const handlePrintCert = () => {
    setCertOpen(true);
    requestAnimationFrame(() => {
      window.print();
    });
  };

  return (
    <RoleGuard
      allowedRoles={ALLOWED}
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 text-zinc-800 dark:bg-zinc-950 dark:text-zinc-200">
          <div className="max-w-md space-y-3 rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Acceso restringido</h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Solo usuarios con rol owner o traffic_manager pueden generar auditorías ESG Enterprise.
            </p>
          </div>
        </div>
      }
    >
      <div className="min-h-screen bg-zinc-50 text-zinc-800 dark:bg-zinc-950 dark:text-zinc-200">
        <style
          dangerouslySetInnerHTML={{
            __html: `
            @media print {
              .esg-no-print { display: none !important; }
              .esg-modal-shell { position: static !important; }
              .esg-print-surface { box-shadow: none !important; border: 1px solid #e2e8f0 !important; }
            }
          `,
          }}
        />

        <header className="border-b border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800/80 dark:bg-zinc-900/90">
          <div className="max-w-6xl mx-auto px-6 py-5 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400/90">
                Enterprise ESG
              </p>
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                Auditoría de huella de carbono
              </h1>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                Portes facturados · certificación de flota · escenario de optimización
              </p>
              <nav className="mt-3 flex flex-wrap gap-2 text-sm">
                <span className="rounded-lg border border-emerald-300 dark:border-emerald-800/60 bg-emerald-100 dark:bg-emerald-950/30 px-3 py-1.5 text-emerald-700 dark:text-emerald-200">
                  Auditoría
                </span>
                <Link
                  href="/sostenibilidad/calidad-km"
                  className="rounded-lg border border-zinc-300 px-3 py-1.5 text-zinc-700 transition hover:border-emerald-600 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-emerald-500 dark:hover:text-zinc-100"
                >
                  Calidad km (mes)
                </Link>
              </nav>
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="mb-1 block text-[10px] uppercase text-zinc-600 dark:text-zinc-500">Desde</label>
                <input
                  type="date"
                  value={fechaInicio}
                  onChange={(e) => setFechaInicio(e.target.value)}
                  className="rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] uppercase text-zinc-600 dark:text-zinc-500">Hasta</label>
                <input
                  type="date"
                  value={fechaFin}
                  onChange={(e) => setFechaFin(e.target.value)}
                  className="rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                />
              </div>
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="mt-5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {loading ? "Actualizando…" : "Actualizar"}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-6 py-8 space-y-8 print:hidden">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-zinc-700 bg-gradient-to-br from-[#111827] to-[#0f1623] p-5 shadow-lg shadow-black/40">
              <p className="text-xs uppercase tracking-wide text-slate-400">Total huella</p>
              <p className="mt-1 text-3xl font-bold tabular-nums text-white">
                {data ? data.total_huella_carbono_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 }) : "—"}
              </p>
              <p className="mt-2 text-xs text-slate-400">kg CO₂ (periodo)</p>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <p className="text-xs uppercase tracking-wide text-zinc-600 dark:text-zinc-500">Emisiones Euro V</p>
              <p className="text-3xl font-bold text-orange-400 mt-1 tabular-nums">
                {data ? `${data.porcentaje_emisiones_euro_v.toFixed(1)}%` : "—"}
              </p>
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-500">del total en el periodo</p>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <p className="text-xs uppercase tracking-wide text-zinc-600 dark:text-zinc-500">Emisiones Euro VI</p>
              <p className="text-3xl font-bold text-emerald-400 mt-1 tabular-nums">
                {data ? `${data.porcentaje_emisiones_euro_vi.toFixed(1)}%` : "—"}
              </p>
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-500">del total en el periodo</p>
            </div>
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900/40 dark:bg-emerald-950/20">
              <p className="text-xs uppercase tracking-wide text-emerald-800 dark:text-emerald-400/80">Ahorro escenario</p>
              <p className="mt-1 text-3xl font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
                {data ? data.co2_ahorro_escenario_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 }) : "—"}
              </p>
              <p className="mt-2 text-xs text-emerald-800/90 dark:text-zinc-500">
                kg CO₂ (escenario {data ? Math.round(data.escenario_optimizacion_pct) : 25}% Euro V → Euro VI)
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Desglose por certificación de flota</h2>
              <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">Distribución % de la huella por norma de emisiones</p>
              <div className="h-[320px] w-full">
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={56}
                        outerRadius={100}
                        paddingAngle={2}
                      >
                        {pieData.map((entry) => (
                          <Cell key={entry.name} fill={PIE_COLORS[entry.name] ?? "#64748b"} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value, _name, item) => {
                          const payload = item?.payload as { co2_kg?: number } | undefined;
                          const kg = payload?.co2_kg ?? 0;
                          return [
                            `${Number(value ?? 0).toFixed(1)}% · ${kg.toFixed(2)} kg`,
                            "Huella",
                          ];
                        }}
                        contentStyle={{ background: "#0f1623", border: "1px solid #334155", borderRadius: 8 }}
                        labelStyle={{ color: "#e2e8f0" }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-zinc-600 dark:text-zinc-500">
                    Sin datos para el periodo seleccionado
                  </div>
                )}
              </div>
            </section>

            <section className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Top 5 clientes (huella)</h2>
              <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">Mayor impacto asociado en kg CO₂</p>
              <ul className="space-y-3 flex-1">
                {(data?.top_clientes ?? []).map((c, i) => (
                  <li
                    key={c.cliente_id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800/80 dark:bg-zinc-950"
                  >
                    <div className="min-w-0">
                      <span className="text-xs text-zinc-600 dark:text-zinc-500">#{i + 1}</span>
                      <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        {c.cliente_nombre || c.cliente_id.slice(0, 8) + "…"}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold tabular-nums text-emerald-700 dark:text-emerald-400/90">
                      {c.co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg
                    </span>
                  </li>
                ))}
                {data && data.top_clientes.length === 0 && (
                  <li className="text-sm text-zinc-600 dark:text-zinc-500">Sin clientes en el periodo.</li>
                )}
              </ul>
            </section>
          </div>

          <section className="rounded-2xl border border-zinc-700 bg-gradient-to-r from-[#0f1623] to-[#111827] p-6">
            <h2 className="mb-2 text-lg font-semibold text-white">Insight de optimización</h2>
            <p className="text-sm leading-relaxed text-slate-200 md:text-base">
              {data?.insight_optimizacion ?? "Carga el informe para ver el insight."}
            </p>
          </section>

          <section className="esg-no-print space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Verificación externa y export ISO (sin PII)</h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Registro de certificados con QR público, export agregado ISO 14083 para terceros y cierre manual{" "}
              <span className="text-emerald-400 font-mono text-xs">externally_verified</span> (solo propietario).
              Documentación en{" "}
              <Link href="/help/esg-external-verification" className="text-emerald-400 underline">
                /help/esg-external-verification
              </Link>
              . Webhook para certificadora:{" "}
              <code className="text-xs text-zinc-500 dark:text-zinc-400">POST /api/v1/webhooks/esg-external-verify</code> con firma{" "}
              <code className="text-xs text-zinc-500 dark:text-zinc-400">X-ABL-ESG-Signature</code>.
            </p>

            {flowErr ? <p className="text-xs text-rose-400">{flowErr}</p> : null}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={exportBusy !== null}
                onClick={() => void onExportIso("csv", false)}
                className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-800 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800 dark:hover:bg-zinc-700"
              >
                {exportBusy === "csv" ? "Generando…" : "Descargar CSV ISO (periodo)"}
              </button>
              <button
                type="button"
                disabled={exportBusy !== null}
                onClick={() => void onExportIso("json", false)}
                className="rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-800 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800 dark:hover:bg-zinc-700"
              >
                {exportBusy === "json" ? "Generando…" : "Descargar JSON ISO (periodo)"}
              </button>
              <button
                type="button"
                disabled={exportBusy !== null}
                onClick={() => void onExportIso("json", true)}
                className="px-4 py-2 rounded-lg bg-emerald-950/50 text-emerald-200 text-sm font-medium border border-emerald-800 hover:bg-emerald-900/40 disabled:opacity-50"
              >
                {exportBusy === "json_auditor" ? "Generando…" : "JSON para auditor (sin empresa_id en meta)"}
              </button>
            </div>

            {jwtRbacRole() === "owner" ? (
              <div className="space-y-2 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-500">Cerrar verificación (owner)</p>
                <div className="flex flex-wrap gap-2 items-center">
                  <input
                    type="text"
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    placeholder="verification_code (UUID)"
                    className="min-w-[240px] flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-600"
                  />
                  <button
                    type="button"
                    disabled={verifyLoading}
                    onClick={() => void onVerifyExternal()}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {verifyLoading ? "Actualizando…" : "Marcar externally_verified"}
                  </button>
                </div>
                {verifyMsg ? <p className="text-xs text-zinc-500 dark:text-zinc-400">{verifyMsg}</p> : null}
              </div>
            ) : null}

            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Certificados recientes</h3>
                <button
                  type="button"
                  onClick={() => void loadRegistry()}
                  disabled={registryLoading}
                  className="text-xs text-emerald-400 hover:underline disabled:opacity-50"
                >
                  {registryLoading ? "Cargando…" : "Actualizar lista"}
                </button>
              </div>
              {registryErr ? (
                <p className="text-xs text-rose-400 mb-2">{registryErr}</p>
              ) : null}
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                <table className="w-full text-left text-xs text-zinc-700 dark:text-zinc-300">
                  <thead className="bg-zinc-100 uppercase tracking-wide text-zinc-600 dark:bg-zinc-900/80 dark:text-zinc-500">
                    <tr>
                      <th className="px-3 py-2">Código (QR)</th>
                      <th className="px-3 py-2">Estado</th>
                      <th className="px-3 py-2">Tipo</th>
                      <th className="px-3 py-2">Emitido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registry.map((r) => (
                      <tr key={r.verification_code} className="border-t border-zinc-200 dark:border-zinc-800/80">
                        <td className="px-3 py-2 font-mono text-[11px] break-all">{r.verification_code}</td>
                        <td className="px-3 py-2">{r.verification_status}</td>
                        <td className="px-3 py-2">{r.subject_type}</td>
                        <td className="px-3 py-2 text-zinc-600 dark:text-zinc-500">
                          {r.created_at ? r.created_at.slice(0, 19).replace("T", " ") : "—"}
                        </td>
                      </tr>
                    ))}
                    {!registryLoading && registry.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-4 text-center text-zinc-600 dark:text-zinc-500">
                          Sin certificados registrados.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setCertOpen(true)}
              className="rounded-xl bg-zinc-100 px-5 py-2.5 text-sm font-semibold text-zinc-900 transition-colors hover:bg-white dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            >
              Descargar Certificado ESG (PDF)
            </button>
          </div>
        </main>

        {certOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <button
              type="button"
              aria-label="Cerrar"
              className="esg-no-print absolute inset-0 bg-black/70"
              onClick={() => setCertOpen(false)}
            />
            <div className="esg-modal-shell relative z-10 max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-zinc-300 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-900 print:max-h-none print:overflow-visible print:border-0 print:bg-white print:shadow-none">
              <div className="esg-no-print flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Certificado ESG (vista previa)</h3>
                <button
                  type="button"
                  onClick={() => setCertOpen(false)}
                  className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  Cerrar
                </button>
              </div>
              <div className="p-6 space-y-4">
                <div
                  id="esg-print-root"
                  className="esg-print-surface rounded-xl border border-slate-200 bg-white text-slate-900 p-8"
                >
                  <div className="flex justify-between items-start border-b border-slate-200 pb-4 mb-6">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-zinc-600 dark:text-zinc-500">Certificado</p>
                      <h4 className="text-xl font-bold text-slate-900 mt-1">Auditoría de huella de carbono</h4>
                      <p className="text-sm text-slate-600 mt-1">AB Logistics OS · Enterprise ESG</p>
                    </div>
                    <div className="text-right text-sm text-slate-600">
                      <p>
                        Periodo: {data?.fecha_inicio ?? "—"} — {data?.fecha_fin ?? "—"}
                      </p>
                    </div>
                  </div>
                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-zinc-600 dark:text-zinc-500">Huella total declarada</dt>
                      <dd className="font-semibold text-lg">
                        {data != null
                          ? `${data.total_huella_carbono_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg CO₂`
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-zinc-600 dark:text-zinc-500">Euro V / Euro VI (% sobre total)</dt>
                      <dd className="font-semibold">
                        {data != null
                          ? `${data.porcentaje_emisiones_euro_v.toFixed(1)}% / ${data.porcentaje_emisiones_euro_vi.toFixed(1)}%`
                          : "—"}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-zinc-600 dark:text-zinc-500">Insight de optimización</dt>
                      <dd className="mt-1 text-slate-800">{data?.insight_optimizacion ?? "—"}</dd>
                    </div>
                  </dl>
                  <p className="mt-8 border-t border-slate-200 pt-4 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-500">
                    Documento generado para fines de auditoría interna. Los cálculos se basan en portes facturados y
                    certificación de flota registrada en el sistema.
                  </p>
                </div>
                <div className="esg-no-print flex gap-3 justify-end">
                  <button
                    type="button"
                    onClick={() => setCertOpen(false)}
                    className="rounded-lg border border-zinc-300 px-4 py-2 text-sm text-zinc-700 dark:border-zinc-600 dark:text-zinc-300"
                  >
                    Cerrar
                  </button>
                  <button
                    type="button"
                    onClick={handlePrintCert}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
                  >
                    Imprimir / Guardar como PDF
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </RoleGuard>
  );
}
