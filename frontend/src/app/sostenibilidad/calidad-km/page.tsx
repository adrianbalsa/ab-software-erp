"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchEsgQualityReport,
  type AppRbacRole,
  type EsgQualityReport,
} from "@/lib/api";

const ALLOWED: AppRbacRole[] = ["owner", "traffic_manager", "admin"];

const SOURCE_LABELS: Record<string, string> = {
  route_api_meters: "Routes API (metros)",
  recorded_road_km: "Km carretera registrados",
  telemetry: "Telemetría",
  estimated: "Solo estimado",
};

function defaultCalendarMonth() {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function pctFmt(n: number) {
  return `${n.toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

export default function EsgCalidadKmPage() {
  const { year: y0, month: m0 } = useMemo(() => defaultCalendarMonth(), []);
  const [year, setYear] = useState(y0);
  const [month, setMonth] = useState(m0);
  const [data, setData] = useState<EsgQualityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rep = await fetchEsgQualityReport(year, month);
      setData(rep);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "Error al cargar el reporte");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  const monthLabel = useMemo(() => {
    try {
      return new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(
        new Date(year, month - 1, 1),
      );
    } catch {
      return `${month}/${year}`;
    }
  }, [year, month]);

  return (
    <RoleGuard
      allowedRoles={ALLOWED}
      fallback={
        <AppShell active="sostenibilidad">
          <div className="mx-auto mt-10 max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 text-center">
            <h1 className="text-lg font-semibold text-zinc-100">Acceso restringido</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Solo owner, traffic_manager o admin pueden ver el reporte de calidad km ESG.
            </p>
          </div>
        </AppShell>
      }
    >
      <AppShell active="sostenibilidad">
        <div className="mx-auto max-w-5xl px-3 py-6 sm:px-4 lg:px-8">
          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-500/90">ESG · Trazabilidad</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-zinc-50">Calidad de datos km</h1>
              <p className="mt-1 max-w-2xl text-sm text-zinc-400">
                Portes facturados del mes: cobertura por fuente, km medido vs estimado (misma lógica que el cierre
                mensual). API:{" "}
                <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-zinc-500">
                  GET /api/v1/esg/quality-report
                </code>
              </p>
              <nav className="mt-3 flex flex-wrap gap-2 text-sm">
                <Link
                  href="/sostenibilidad/auditoria"
                  className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-3 py-1.5 text-zinc-300 transition hover:border-zinc-600 hover:text-white"
                >
                  ← Auditoría de huella
                </Link>
                <span className="self-center text-zinc-600">·</span>
                <span className="self-center text-zinc-500">Mes calendario</span>
              </nav>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  Año
                </label>
                <input
                  type="number"
                  min={2000}
                  max={2100}
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value) || year)}
                  className="w-24 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  Mes
                </label>
                <select
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                  className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
                >
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <option key={m} value={m}>
                      {m.toString().padStart(2, "0")}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="mt-5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {loading ? "Cargando…" : "Actualizar"}
              </button>
            </div>
          </div>

          {error ? (
            <div className="mb-6 rounded-xl border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          {data ? (
            <div className="space-y-6">
              <p className="text-sm text-zinc-500">
                Periodo: <span className="font-medium capitalize text-zinc-300">{monthLabel}</span> ·{" "}
                {data.num_portes_facturados} porte(s) facturado(s)
              </p>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Card className="border-zinc-800 bg-zinc-900/40">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-300">Km actividad (suma)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold tabular-nums text-zinc-50">
                      {data.km_coverage.total_km_activity.toLocaleString("es-ES", {
                        maximumFractionDigits: 2,
                      })}
                    </p>
                    <CardDescription className="mt-1">Peso operativo por porte</CardDescription>
                  </CardContent>
                </Card>
                <Card className="border-zinc-800 bg-zinc-900/40">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-300">Km medido</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold tabular-nums text-emerald-400">
                      {pctFmt(data.pct_measured_km_activity)}
                    </p>
                    <CardDescription className="mt-1">No estimado (rutas + carretera + telemetría)</CardDescription>
                  </CardContent>
                </Card>
                <Card className="border-zinc-800 bg-zinc-900/40">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-300">Km estimado</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold tabular-nums text-amber-400">
                      {pctFmt(data.pct_estimated_km_activity)}
                    </p>
                    <CardDescription className="mt-1">Sobre km de actividad del mes</CardDescription>
                  </CardContent>
                </Card>
                <Card className="border-zinc-800 bg-zinc-900/40">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-300">Fuentes (porte)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold tabular-nums text-zinc-50">
                      {Object.values(data.portes_by_source).reduce((a, b) => a + b, 0)}
                    </p>
                    <CardDescription className="mt-1">Conteo por clasificación inferida</CardDescription>
                  </CardContent>
                </Card>
              </div>

              <Card className="border-zinc-800 bg-zinc-900/40">
                <CardHeader>
                  <CardTitle className="text-zinc-100">Cobertura por fuente (% del km de actividad)</CardTitle>
                  <CardDescription>Coherente con el payload del cierre ESG mensual</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    {(
                      [
                        ["route_api_meters", data.km_coverage.pct_km_route_api_meters],
                        ["recorded_road_km", data.km_coverage.pct_km_recorded_road_km],
                        ["telemetry", data.km_coverage.pct_km_telemetry],
                        ["estimated", data.km_coverage.pct_km_estimated],
                      ] as const
                    ).map(([key, pct]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-4 py-3"
                      >
                        <dt className="text-sm text-zinc-400">{SOURCE_LABELS[key] ?? key}</dt>
                        <dd className="text-sm font-semibold tabular-nums text-zinc-100">{pctFmt(pct)}</dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>

              <Card className="border-zinc-800 bg-zinc-900/40">
                <CardHeader>
                  <CardTitle className="text-zinc-100">Portes por fuente</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800">
                    {Object.entries(data.portes_by_source).map(([key, n]) => (
                      <li key={key} className="flex justify-between px-4 py-2.5 text-sm">
                        <span className="text-zinc-400">{SOURCE_LABELS[key] ?? key}</span>
                        <span className="font-medium tabular-nums text-zinc-100">{n}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <Card className="border-zinc-800 bg-zinc-900/40">
                <CardHeader>
                  <CardTitle className="text-zinc-100">Gaps y alertas</CardTitle>
                  <CardDescription>
                    {data.gaps.length === 0
                      ? "Sin incidencias de calidad detectadas para este mes."
                      : "Revise el detalle antes del cierre ESG o auditoría externa."}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {data.gaps.length === 0 ? (
                    <p className="text-sm text-zinc-500">—</p>
                  ) : (
                    <ul className="space-y-3">
                      {data.gaps.map((g, i) => (
                        <li
                          key={`${g.kind}-${i}`}
                          className="rounded-lg border border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm"
                        >
                          <p className="font-mono text-xs text-amber-500/90">{g.kind}</p>
                          <p className="mt-1 text-zinc-200">{g.detail}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : !loading && !error ? (
            <p className="text-sm text-zinc-500">Sin datos.</p>
          ) : null}
        </div>
      </AppShell>
    </RoleGuard>
  );
}
