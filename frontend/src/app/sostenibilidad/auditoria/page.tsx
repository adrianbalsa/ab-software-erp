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
      setError(e instanceof Error ? e.message : "Error al cargar el informe");
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
      setRegistryErr(e instanceof Error ? e.message : "No se pudo cargar el registro de certificados");
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
      setFlowErr(e instanceof Error ? e.message : "Error al exportar");
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
      setVerifyMsg(e instanceof Error ? e.message : "No se pudo actualizar el certificado");
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
        <div className="min-h-screen bg-[#0a0e17] text-slate-200 flex items-center justify-center p-8">
          <div className="max-w-md text-center space-y-3 border border-slate-800 rounded-2xl p-8 bg-[#0f1623]">
            <h1 className="text-xl font-semibold text-white">Acceso restringido</h1>
            <p className="text-sm text-slate-400">
              Solo usuarios con rol owner o traffic_manager pueden generar auditorías ESG Enterprise.
            </p>
          </div>
        </div>
      }
    >
      <div className="min-h-screen bg-[#0a0e17] text-slate-200">
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

        <header className="border-b border-slate-800/80 bg-[#0f1623]/90 backdrop-blur">
          <div className="max-w-6xl mx-auto px-6 py-5 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400/90">
                Enterprise ESG
              </p>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Auditoría de huella de carbono
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Portes facturados · certificación de flota · escenario de optimización
              </p>
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-[10px] uppercase text-slate-500 mb-1">Desde</label>
                <input
                  type="date"
                  value={fechaInicio}
                  onChange={(e) => setFechaInicio(e.target.value)}
                  className="bg-[#0a0e17] border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase text-slate-500 mb-1">Hasta</label>
                <input
                  type="date"
                  value={fechaFin}
                  onChange={(e) => setFechaFin(e.target.value)}
                  className="bg-[#0a0e17] border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"
                />
              </div>
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="mt-5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold disabled:opacity-50"
              >
                {loading ? "Actualizando…" : "Actualizar"}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-6 py-8 space-y-8 print:hidden">
          {error && (
            <div className="rounded-xl border border-red-900/50 bg-red-950/40 text-red-200 px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-slate-800 bg-gradient-to-br from-[#111827] to-[#0f1623] p-5 shadow-lg shadow-black/40">
              <p className="text-xs uppercase tracking-wide text-slate-500">Total huella</p>
              <p className="text-3xl font-bold text-white mt-1 tabular-nums">
                {data ? data.total_huella_carbono_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 }) : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-2">kg CO₂ (periodo)</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-[#0f1623] p-5">
              <p className="text-xs uppercase tracking-wide text-slate-500">Emisiones Euro V</p>
              <p className="text-3xl font-bold text-orange-400 mt-1 tabular-nums">
                {data ? `${data.porcentaje_emisiones_euro_v.toFixed(1)}%` : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-2">del total en el periodo</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-[#0f1623] p-5">
              <p className="text-xs uppercase tracking-wide text-slate-500">Emisiones Euro VI</p>
              <p className="text-3xl font-bold text-emerald-400 mt-1 tabular-nums">
                {data ? `${data.porcentaje_emisiones_euro_vi.toFixed(1)}%` : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-2">del total en el periodo</p>
            </div>
            <div className="rounded-2xl border border-emerald-900/40 bg-emerald-950/20 p-5">
              <p className="text-xs uppercase tracking-wide text-emerald-400/80">Ahorro escenario</p>
              <p className="text-3xl font-bold text-emerald-300 mt-1 tabular-nums">
                {data ? data.co2_ahorro_escenario_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 }) : "—"}
              </p>
              <p className="text-xs text-slate-500 mt-2">
                kg CO₂ (escenario {data ? Math.round(data.escenario_optimizacion_pct) : 25}% Euro V → Euro VI)
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <section className="rounded-2xl border border-slate-800 bg-[#0f1623] p-6">
              <h2 className="text-lg font-semibold text-white mb-1">Desglose por certificación de flota</h2>
              <p className="text-sm text-slate-500 mb-4">Distribución % de la huella por norma de emisiones</p>
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
                  <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                    Sin datos para el periodo seleccionado
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-[#0f1623] p-6 flex flex-col">
              <h2 className="text-lg font-semibold text-white mb-1">Top 5 clientes (huella)</h2>
              <p className="text-sm text-slate-500 mb-4">Mayor impacto asociado en kg CO₂</p>
              <ul className="space-y-3 flex-1">
                {(data?.top_clientes ?? []).map((c, i) => (
                  <li
                    key={c.cliente_id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-[#0a0e17] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <span className="text-xs text-slate-500">#{i + 1}</span>
                      <p className="text-sm font-medium text-slate-100 truncate">
                        {c.cliente_nombre || c.cliente_id.slice(0, 8) + "…"}
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-emerald-400/90 tabular-nums shrink-0">
                      {c.co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg
                    </span>
                  </li>
                ))}
                {data && data.top_clientes.length === 0 && (
                  <li className="text-sm text-slate-500">Sin clientes en el periodo.</li>
                )}
              </ul>
            </section>
          </div>

          <section className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0f1623] to-[#111827] p-6">
            <h2 className="text-lg font-semibold text-white mb-2">Insight de optimización</h2>
            <p className="text-slate-300 leading-relaxed text-sm md:text-base">
              {data?.insight_optimizacion ?? "Carga el informe para ver el insight."}
            </p>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-[#0f1623] p-6 space-y-4 esg-no-print">
            <h2 className="text-lg font-semibold text-white">Verificación externa y export ISO (sin PII)</h2>
            <p className="text-sm text-slate-500">
              Registro de certificados con QR público, export agregado ISO 14083 para terceros y cierre manual{" "}
              <span className="text-emerald-400 font-mono text-xs">externally_verified</span> (solo propietario).
              Documentación en{" "}
              <Link href="/help/esg-external-verification" className="text-emerald-400 underline">
                /help/esg-external-verification
              </Link>
              . Webhook para certificadora:{" "}
              <code className="text-xs text-slate-400">POST /api/v1/webhooks/esg-external-verify</code> con firma{" "}
              <code className="text-xs text-slate-400">X-ABL-ESG-Signature</code>.
            </p>

            {flowErr ? <p className="text-xs text-rose-400">{flowErr}</p> : null}

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={exportBusy !== null}
                onClick={() => void onExportIso("csv", false)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-100 text-sm font-medium border border-slate-600 hover:bg-slate-700 disabled:opacity-50"
              >
                {exportBusy === "csv" ? "Generando…" : "Descargar CSV ISO (periodo)"}
              </button>
              <button
                type="button"
                disabled={exportBusy !== null}
                onClick={() => void onExportIso("json", false)}
                className="px-4 py-2 rounded-lg bg-slate-800 text-slate-100 text-sm font-medium border border-slate-600 hover:bg-slate-700 disabled:opacity-50"
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
              <div className="rounded-xl border border-slate-800 bg-[#0a0e17] p-4 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cerrar verificación (owner)</p>
                <div className="flex flex-wrap gap-2 items-center">
                  <input
                    type="text"
                    value={verifyCode}
                    onChange={(e) => setVerifyCode(e.target.value)}
                    placeholder="verification_code (UUID)"
                    className="min-w-[240px] flex-1 bg-[#0f1623] border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600"
                  />
                  <button
                    type="button"
                    disabled={verifyLoading}
                    onClick={() => void onVerifyExternal()}
                    className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {verifyLoading ? "Actualizando…" : "Marcar externally_verified"}
                  </button>
                </div>
                {verifyMsg ? <p className="text-xs text-slate-400">{verifyMsg}</p> : null}
              </div>
            ) : null}

            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <h3 className="text-sm font-semibold text-slate-200">Certificados recientes</h3>
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
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-900/80 text-slate-500 uppercase tracking-wide">
                    <tr>
                      <th className="px-3 py-2">Código (QR)</th>
                      <th className="px-3 py-2">Estado</th>
                      <th className="px-3 py-2">Tipo</th>
                      <th className="px-3 py-2">Emitido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registry.map((r) => (
                      <tr key={r.verification_code} className="border-t border-slate-800/80">
                        <td className="px-3 py-2 font-mono text-[11px] break-all">{r.verification_code}</td>
                        <td className="px-3 py-2">{r.verification_status}</td>
                        <td className="px-3 py-2">{r.subject_type}</td>
                        <td className="px-3 py-2 text-slate-500">
                          {r.created_at ? r.created_at.slice(0, 19).replace("T", " ") : "—"}
                        </td>
                      </tr>
                    ))}
                    {!registryLoading && registry.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-4 text-slate-500 text-center">
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
              className="px-5 py-2.5 rounded-xl bg-slate-100 text-slate-900 font-semibold text-sm hover:bg-white transition-colors"
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
            <div className="esg-modal-shell relative bg-[#0f1623] border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl z-10 print:max-h-none print:overflow-visible print:border-0 print:shadow-none print:bg-white">
              <div className="esg-no-print flex justify-between items-center px-6 py-4 border-b border-slate-800">
                <h3 className="text-white font-semibold">Certificado ESG (vista previa)</h3>
                <button
                  type="button"
                  onClick={() => setCertOpen(false)}
                  className="text-slate-400 hover:text-white text-sm"
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
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Certificado</p>
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
                      <dt className="text-slate-500">Huella total declarada</dt>
                      <dd className="font-semibold text-lg">
                        {data != null
                          ? `${data.total_huella_carbono_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg CO₂`
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Euro V / Euro VI (% sobre total)</dt>
                      <dd className="font-semibold">
                        {data != null
                          ? `${data.porcentaje_emisiones_euro_v.toFixed(1)}% / ${data.porcentaje_emisiones_euro_vi.toFixed(1)}%`
                          : "—"}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-slate-500">Insight de optimización</dt>
                      <dd className="mt-1 text-slate-800">{data?.insight_optimizacion ?? "—"}</dd>
                    </div>
                  </dl>
                  <p className="mt-8 text-xs text-slate-500 border-t border-slate-200 pt-4">
                    Documento generado para fines de auditoría interna. Los cálculos se basan en portes facturados y
                    certificación de flota registrada en el sistema.
                  </p>
                </div>
                <div className="esg-no-print flex gap-3 justify-end">
                  <button
                    type="button"
                    onClick={() => setCertOpen(false)}
                    className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 text-sm"
                  >
                    Cerrar
                  </button>
                  <button
                    type="button"
                    onClick={handlePrintCert}
                    className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold"
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
