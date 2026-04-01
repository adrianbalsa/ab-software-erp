"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  Car,
  Download,
  Fuel,
  Loader2,
  RefreshCw,
  Wrench,
} from "lucide-react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { AppShell } from "@/components/AppShell";
import { API_BASE, apiFetch } from "@/lib/api";

type VehiculoRow = {
  id: string;
  matricula: string;
  vehiculo: string;
  estado: string;
  km_actual: number;
  tipo_motor: string;
  itv_vencimiento?: string | null;
  seguro_vencimiento?: string | null;
  km_proximo_servicio?: number | null;
};

type Metricas = {
  total_vehiculos: number;
  en_riesgo_parada: number;
  disponibles: number;
  pct_disponible: number;
  pct_riesgo_parada: number;
};

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  return String(s).slice(0, 10);
}

function badgeEstado(estado: string): string {
  const e = estado || "";
  if (e === "Operativo") return "bg-emerald-100 text-emerald-900 border-emerald-300";
  if (e === "En Taller") return "bg-amber-100 text-amber-900 border-amber-300";
  if (e === "Baja" || e === "Vendido") return "bg-slate-200 text-slate-800 border-slate-400";
  return "bg-slate-100 text-slate-800 border-slate-300";
}

function badgeFecha(label: string, iso: string | null | undefined): ReactNode {
  if (!iso) {
    return (
      <span className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
        Sin {label}
      </span>
    );
  }
  const d = new Date(iso);
  const days = Math.ceil((d.getTime() - Date.now()) / (86400 * 1000));
  let cls =
    "border-emerald-300 bg-emerald-50 text-emerald-900";
  if (days < 0) cls = "border-red-400 bg-red-50 text-red-900 font-semibold";
  else if (days <= 30) cls = "border-red-300 bg-red-50 text-red-900";
  else if (days <= 60) cls = "border-amber-300 bg-amber-50 text-amber-900";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs ${cls}`}
      title={`${label}: ${iso.slice(0, 10)}`}
    >
      {fmtDate(iso)}
    </span>
  );
}

export default function FlotaPage() {
  const [rows, setRows] = useState<VehiculoRow[]>([]);
  const [metricas, setMetricas] = useState<Metricas | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rInv, rMet] = await Promise.all([
        apiFetch(`${API_BASE}/flota/inventario`, {
          credentials: "include",
        }),
        apiFetch(`${API_BASE}/flota/metricas`, {
          credentials: "include",
        }),
      ]);
      if (!rInv.ok) {
        const err = await rInv.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${rInv.status}`);
      }
      if (!rMet.ok) {
        const err = await rMet.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${rMet.status}`);
      }
      setRows((await rInv.json()) as VehiculoRow[]);
      setMetricas((await rMet.json()) as Metricas);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setRows([]);
      setMetricas(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const res = await apiFetch(`${API_BASE}/flota/export`, {
        credentials: "include",
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `estado_flota_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "No se pudo exportar");
    } finally {
      setExporting(false);
    }
  };

  const chartData =
    metricas && metricas.total_vehiculos > 0
      ? [
          { name: "Flota disponible", value: metricas.pct_disponible, fill: "#2563eb" },
          { name: "Riesgo de parada", value: metricas.pct_riesgo_parada, fill: "#fbbf24" },
        ]
      : [];

  return (
    <AppShell active="flota">
      <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "#0b1224" }}>
            Flota
          </h1>
          <p className="text-sm text-slate-500">
            Estado de vehículos, vencimientos y disponibilidad
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href="/flota/combustible"
            className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-bold text-emerald-900 hover:bg-emerald-100"
          >
            <Fuel className="w-4 h-4" />
            Combustible (CSV)
          </Link>
          <Link
            href="/flota/mantenimiento"
            className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-bold text-amber-900 hover:bg-amber-100"
          >
            <Wrench className="w-4 h-4" />
            Taller / mantenimiento
          </Link>
          <button
            type="button"
            onClick={() => void exportCsv()}
            disabled={exporting || loading}
            className="inline-flex items-center gap-2 rounded-xl border border-[#2563eb]/40 bg-white px-4 py-2 text-sm font-bold text-[#2563eb] hover:bg-[#2563eb]/5 disabled:opacity-50"
          >
            {exporting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Exportar estado de flota
          </button>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </button>
        </div>
      </header>

      <main className="p-8 flex-1 overflow-y-auto space-y-8 max-w-7xl">
        {error && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {error} (¿iniciaste sesión?)
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div
            className="rounded-2xl border p-6"
            style={{ borderColor: "#e2e8f0", background: "#fff" }}
          >
            <h2 className="text-lg font-bold flex items-center gap-2 mb-4" style={{ color: "#0b1224" }}>
              <Car className="w-5 h-5 text-[#2563eb]" />
              Disponibilidad de flota
            </h2>
            {loading ? (
              <p className="text-slate-500 text-sm py-12 text-center">Cargando gráfico…</p>
            ) : metricas && metricas.total_vehiculos === 0 ? (
              <p className="text-slate-500 text-sm py-8 text-center">Sin vehículos en inventario.</p>
            ) : (
              <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                    >
                      {chartData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} stroke="#fff" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => [`${Number(v ?? 0)}%`, ""]}
                      contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0" }}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
            {metricas && metricas.total_vehiculos > 0 && (
              <p className="text-xs text-slate-500 mt-2 text-center">
                Riesgo = no operativo o alerta de prioridad alta · Total {metricas.total_vehiculos}{" "}
                vehículos
              </p>
            )}
          </div>

          <div
            className="rounded-2xl border p-6 flex flex-col justify-center"
            style={{
              borderColor: "#e2e8f0",
              background: "linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)",
            }}
          >
            <Wrench className="w-8 h-8 text-[#2563eb] mb-3" />
            <h3 className="font-bold text-lg" style={{ color: "#0b1224" }}>
              Taller y cumplimiento
            </h3>
            <p className="text-sm text-slate-600 mt-2 leading-relaxed">
              Exporta un CSV con ITV, seguro, km de revisión y márgenes de días para el jefe de taller.
              Columnas separadas por punto y coma, listo para Excel.
            </p>
            <button
              type="button"
              onClick={() => void exportCsv()}
              disabled={exporting}
              className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold text-white shadow-md"
              style={{ background: "#2563eb" }}
            >
              {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Exportar estado de flota
            </button>
          </div>
        </div>

        <div
          className="rounded-2xl border overflow-hidden"
          style={{ borderColor: "#e2e8f0", background: "#fff" }}
        >
          <div
            className="px-6 py-4 border-b flex items-center gap-2"
            style={{ borderColor: "#e2e8f0", background: "#f8fafc" }}
          >
            <Car className="w-5 h-5 text-[#2563eb]" />
            <h2 className="font-bold text-lg" style={{ color: "#0b1224" }}>
              Inventario detallado
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="px-4 py-3 font-semibold">Matrícula</th>
                  <th className="px-4 py-3 font-semibold">Vehículo</th>
                  <th className="px-4 py-3 font-semibold">Estado</th>
                  <th className="px-4 py-3 font-semibold">ITV</th>
                  <th className="px-4 py-3 font-semibold">Seguro</th>
                  <th className="px-4 py-3 font-semibold">Próx. km servicio</th>
                  <th className="px-4 py-3 font-semibold">Km actual</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                      Cargando…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                      No hay vehículos registrados.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.id} className="border-b border-slate-50 hover:bg-slate-50/80">
                      <td className="px-4 py-3 font-mono font-medium" style={{ color: "#0b1224" }}>
                        {r.matricula}
                      </td>
                      <td className="px-4 py-3 text-slate-800">{r.vehiculo}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-semibold ${badgeEstado(r.estado)}`}
                        >
                          {r.estado}
                        </span>
                      </td>
                      <td className="px-4 py-3">{badgeFecha("ITV", r.itv_vencimiento)}</td>
                      <td className="px-4 py-3">{badgeFecha("Seguro", r.seguro_vencimiento)}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {r.km_proximo_servicio != null ? (
                          <span className="font-mono text-xs">
                            {Number(r.km_proximo_servicio).toLocaleString("es-ES")} km
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700">
                        {Number(r.km_actual).toLocaleString("es-ES")}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
