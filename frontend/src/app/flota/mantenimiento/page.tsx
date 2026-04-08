"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CalendarDays,
  Loader2,
  Wrench,
} from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/AppShell";
import {
  getAlertasMantenimiento,
  postRegistrarMantenimiento,
  type MantenimientoAlerta,
  type MantenimientoAlertaAdmin,
  type MantenimientoAlertaKm,
  isAlertaKm,
} from "@/lib/api";

function pctBar(desgaste: number): number {
  return Math.min(100, Math.max(0, desgaste * 100));
}

function barColor(u: MantenimientoAlertaKm["urgencia"]): string {
  if (u === "CRITICO") return "bg-red-500";
  if (u === "ADVERTENCIA") return "bg-amber-400";
  return "bg-emerald-500";
}

function MantenimientoDashboard() {
  const [rows, setRows] = useState<MantenimientoAlerta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [modalPlan, setModalPlan] = useState<MantenimientoAlertaKm | null>(null);
  const [importe, setImporte] = useState("");
  const [proveedor, setProveedor] = useState("Taller");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAlertasMantenimiento();
      setRows(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar alertas");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rowsKm = rows.filter(isAlertaKm);
  const rowsAdmin = rows.filter((r): r is MantenimientoAlertaAdmin => !isAlertaKm(r));

  const criticos = rowsKm.filter((r) => r.urgencia === "CRITICO");
  const advertencias = rowsKm.filter((r) => r.urgencia === "ADVERTENCIA");
  const adminCriticos = rowsAdmin.filter((r) => r.urgencia === "CRITICO");
  const adminAdvertencias = rowsAdmin.filter((r) => r.urgencia === "ADVERTENCIA");

  const onRegistrar = async () => {
    if (!modalPlan) return;
    const imp = parseFloat(importe.replace(",", "."));
    if (!Number.isFinite(imp) || imp <= 0) {
      setError("Indica un importe válido (> 0).");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const out = await postRegistrarMantenimiento({
        plan_id: modalPlan.plan_id,
        importe_eur: imp,
        proveedor: proveedor.trim() || "Taller",
        concepto: `${modalPlan.tipo_tarea} — ${modalPlan.matricula ?? modalPlan.vehiculo_id.slice(0, 8)}`,
      });
      setSuccess(
        `Mantenimiento registrado (km base ${out.ultimo_km_realizado}). Gasto #${out.gasto_id}.`,
      );
      setModalPlan(null);
      setImporte("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo registrar");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link
            href="/flota"
            className="inline-flex items-center gap-1 text-sm text-[#2563eb] font-medium hover:underline mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Volver a Flota
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Wrench className="w-7 h-7 text-[#2563eb]" />
            Taller — mantenimiento por km
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Desgaste = km desde el último mantenimiento ÷ intervalo. Odómetro acumulado al completar
            portes.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="self-start inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Actualizar
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {success}
        </div>
      )}

      {(criticos.length > 0 || advertencias.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2 mb-6">
          {criticos.length > 0 && (
            <div className="rounded-xl border-2 border-red-300 bg-red-50/80 p-4 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-red-900 mb-2">
                <AlertTriangle className="w-5 h-5" />
                Crítico ({criticos.length})
              </div>
              <ul className="text-sm text-red-950 space-y-1">
                {criticos.map((r) => (
                  <li key={r.plan_id}>
                    <span className="font-mono">{r.matricula ?? "—"}</span> — {r.tipo_tarea} (
                    {(r.desgaste * 100).toFixed(0)}% del intervalo)
                  </li>
                ))}
              </ul>
            </div>
          )}
          {advertencias.length > 0 && (
            <div className="rounded-xl border-2 border-amber-300 bg-amber-50/80 p-4 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-amber-900 mb-2">
                <AlertTriangle className="w-5 h-5" />
                Advertencia ({advertencias.length})
              </div>
              <ul className="text-sm text-amber-950 space-y-1">
                {advertencias.map((r) => (
                  <li key={r.plan_id}>
                    <span className="font-mono">{r.matricula ?? "—"}</span> — {r.tipo_tarea} (
                    {(r.desgaste * 100).toFixed(0)}%)
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {(adminCriticos.length > 0 || adminAdvertencias.length > 0 || rowsAdmin.length > 0) && (
        <section className="mb-8 rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <CalendarDays className="w-6 h-6 text-[#2563eb]" aria-hidden />
            <h2 className="text-lg font-bold text-slate-900">Alertas administrativas</h2>
            <span className="text-xs font-medium text-slate-500">
              ITV, seguro y tacógrafo (fechas en inventario flota)
            </span>
          </div>
          {(adminCriticos.length > 0 || adminAdvertencias.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2 mb-4">
              {adminCriticos.length > 0 && (
                <div className="rounded-xl border border-red-200 bg-red-50/90 px-3 py-2 text-sm text-red-950">
                  <span className="font-semibold">Crítico · trámites:</span>{" "}
                  {adminCriticos.length} (vencido o ≤14 días)
                </div>
              )}
              {adminAdvertencias.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">
                  <span className="font-semibold">Advertencia · trámites:</span>{" "}
                  {adminAdvertencias.length} (15–45 días)
                </div>
              )}
            </div>
          )}
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100 bg-white">
            {rowsAdmin.map((a) => (
              <li
                key={`${a.vehiculo_id}-${a.tipo_tramite}-${a.fecha_vencimiento}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <CalendarDays className="w-4 h-4 shrink-0 text-slate-400" aria-hidden />
                  <span className="font-mono font-medium text-slate-900">
                    {a.matricula ?? a.vehiculo_id.slice(0, 8)}
                  </span>
                  {a.vehiculo && (
                    <span className="text-slate-600 truncate">{a.vehiculo}</span>
                  )}
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                    {a.tipo_tramite}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-right">
                  <span className="text-slate-600">
                    {a.fecha_vencimiento}
                    {a.dias_restantes < 0
                      ? ` · vencido ${-a.dias_restantes}d`
                      : ` · en ${a.dias_restantes}d`}
                  </span>
                  <span
                    className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                      a.urgencia === "CRITICO"
                        ? "bg-red-100 text-red-800"
                        : a.urgencia === "ADVERTENCIA"
                          ? "bg-amber-100 text-amber-900"
                          : "bg-emerald-100 text-emerald-900"
                    }`}
                  >
                    {a.urgencia}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-10 h-10 animate-spin text-slate-400" />
        </div>
      ) : rowsKm.length === 0 && rowsAdmin.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-600 text-sm">
          No hay alertas de mantenimiento por km ni trámites con fechas en{" "}
          <code className="text-xs bg-slate-100 px-1 rounded">public.flota</code>. Configura{" "}
          <code className="text-xs bg-slate-100 px-1 rounded">planes_mantenimiento</code> o fechas
          ITV / seguro / tacógrafo.
        </div>
      ) : rowsKm.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 p-6 text-center text-slate-600 text-sm mb-6">
          No hay planes de mantenimiento por kilómetros. Las alertas administrativas arriba siguen
          activas si hay fechas configuradas.
        </div>
      ) : null}

      {!loading && rowsKm.length > 0 ? (
        <div className="space-y-6">
          {rowsKm.map((r) => (
            <div
              key={r.plan_id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono font-semibold text-slate-900">
                      {r.matricula ?? r.vehiculo_id.slice(0, 8)}
                    </span>
                    {r.vehiculo && (
                      <span className="text-sm text-slate-600">{r.vehiculo}</span>
                    )}
                    <span
                      className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                        r.urgencia === "CRITICO"
                          ? "bg-red-100 text-red-800"
                          : r.urgencia === "ADVERTENCIA"
                            ? "bg-amber-100 text-amber-900"
                            : "bg-emerald-100 text-emerald-900"
                      }`}
                    >
                      {r.urgencia}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 mt-1">
                    <span className="font-medium">{r.tipo_tarea}</span> — cada {r.intervalo_km} km ·
                    último servicio a {r.ultimo_km_realizado} km · odómetro {r.odometro_actual} km
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setModalPlan(r);
                    setImporte("");
                    setProveedor("Taller");
                    setError(null);
                  }}
                  className="shrink-0 inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  <Wrench className="w-4 h-4" />
                  Registrar mantenimiento
                </button>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-500">
                  <span>Progreso hacia el siguiente servicio</span>
                  <span>{(r.desgaste * 100).toFixed(1)}%</span>
                </div>
                <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barColor(r.urgencia)}`}
                    style={{ width: `${pctBar(r.desgaste)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500">
                  {r.km_desde_ultimo} km desde último mantenimiento (intervalo {r.intervalo_km} km)
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {modalPlan && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="mant-dialog-title"
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl border border-slate-200">
            <h2 id="mant-dialog-title" className="text-lg font-bold text-slate-900 mb-1">
              Registrar mantenimiento
            </h2>
            <p className="text-sm text-slate-600 mb-4">
              {modalPlan.tipo_tarea} — {modalPlan.matricula ?? modalPlan.vehiculo_id.slice(0, 8)}.
              Se actualizará el km del último servicio al odómetro actual (
              {modalPlan.odometro_actual} km) y se creará un gasto.
            </p>
            <label className="block text-sm font-medium text-slate-700 mb-1">Importe (EUR)</label>
            <input
              type="text"
              inputMode="decimal"
              value={importe}
              onChange={(e) => setImporte(e.target.value)}
              placeholder="ej. 150.00"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-3"
            />
            <label className="block text-sm font-medium text-slate-700 mb-1">Proveedor / taller</label>
            <input
              type="text"
              value={proveedor}
              onChange={(e) => setProveedor(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm mb-6"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalPlan(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void onRegistrar()}
                className="inline-flex items-center gap-2 rounded-lg bg-[#2563eb] px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function FlotaMantenimientoPage() {
  return (
    <AppShell active="flota">
      <RoleGuard
        allowedRoles={["owner", "traffic_manager"]}
        fallback={
          <div className="max-w-lg mx-auto px-4 py-16 text-center text-slate-600">
            No tienes permiso para ver el taller de mantenimiento.
          </div>
        }
      >
        <MantenimientoDashboard />
      </RoleGuard>
    </AppShell>
  );
}
