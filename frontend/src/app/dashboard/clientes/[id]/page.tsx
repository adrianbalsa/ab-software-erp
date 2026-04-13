"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowLeft, Loader2, Package, Timer, Truck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type ClienteOperationalDetail, type ClienteOperationalEstadoUi } from "@/lib/api";

function formatEUR(value: number): string {
  return value.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

function formatMonthLabel(mes: string): string {
  const parts = mes.split("-");
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  if (!y || !m) return mes;
  return new Date(y, m - 1, 1).toLocaleDateString("es-ES", { month: "short", year: "2-digit" });
}

function formatDateShort(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return String(s).slice(0, 10);
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

function EstadoBadge({ estado }: { estado: ClienteOperationalEstadoUi }) {
  if (estado === "activo") {
    return (
      <span className="inline-flex items-center rounded-full border border-emerald-500/40 bg-emerald-950/45 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-300">
        Activo
      </span>
    );
  }
  if (estado === "riesgo") {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-950/45 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-200">
        Riesgo
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-zinc-600 bg-zinc-900/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">
      Inactivo
    </span>
  );
}

function ClienteDetailContent() {
  const params = useParams();
  const id = typeof params?.id === "string" ? params.id : "";

  const [data, setData] = useState<ClienteOperationalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.clientes.fetchOperationalDetail(id);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar el cliente.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const chartRows = useMemo(
    () =>
      (data?.facturacion_mensual ?? []).map((r) => ({
        periodo: formatMonthLabel(r.mes),
        facturado: r.total_facturado,
      })),
    [data?.facturacion_mensual],
  );

  return (
    <div className="mx-auto w-full max-w-7xl bg-zinc-950 p-6 md:p-8">
      <div className="mb-6">
        <Link
          href="/dashboard/clientes"
          className="inline-flex items-center gap-2 text-sm font-medium text-zinc-400 transition-colors hover:text-emerald-400"
        >
          <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden />
          Volver a Clientes
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/40 py-20 text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden />
          Cargando ficha del cliente…
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-500/35 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">{error}</div>
      ) : data ? (
        <>
          <header className="mb-8 flex flex-col gap-4 border-b border-zinc-800/80 pb-6 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-zinc-100 md:text-3xl">
                {data.cliente.nombre || "Cliente"}
              </h1>
              <p className="mt-2 break-all font-mono text-xs text-zinc-500">
                ID: <span className="text-zinc-400">{data.cliente.id}</span>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <EstadoBadge estado={data.cliente.estado_ui} />
              {data.cliente.email ? (
                <span className="text-sm text-zinc-500">{data.cliente.email}</span>
              ) : null}
            </div>
          </header>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            {/* KPIs — bento wide strip */}
            <Card className="bunker-card border-zinc-800 lg:col-span-12">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg text-zinc-100">Métricas financieras y operativas</CardTitle>
                <CardDescription className="text-zinc-500">Resumen acumulado del cliente en tu tenant.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="rounded-xl border border-emerald-500/25 bg-zinc-950/50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                      <Package className="h-4 w-4 text-emerald-500/90" aria-hidden />
                      Total facturado
                    </div>
                    <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
                      {formatEUR(data.metricas.total_facturado)}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">Suma de todas las facturas emitidas.</p>
                  </div>
                  <div className="rounded-xl border border-zinc-700/80 bg-zinc-950/50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                      <Truck className="h-4 w-4 text-zinc-400" aria-hidden />
                      Portes realizados
                    </div>
                    <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
                      {data.metricas.portes_realizados}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">Operaciones logísticas registradas (todos los estados).</p>
                  </div>
                  <div className="rounded-xl border border-amber-500/20 bg-zinc-950/50 p-4">
                    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                      <Timer className="h-4 w-4 text-amber-500/80" aria-hidden />
                      Días de pago (promedio)
                    </div>
                    <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
                      {data.metricas.dias_pago_promedio != null
                        ? `${data.metricas.dias_pago_promedio} d`
                        : "—"}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      Media en facturas cobradas (emisión → cobro), cuando hay fechas.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Chart */}
            <Card className="bunker-card border-zinc-800 lg:col-span-5">
              <CardHeader className="pb-2">
                <CardTitle className="text-base text-zinc-100">Facturación (6 meses)</CardTitle>
                <CardDescription className="text-zinc-500">Tendencia por mes de emisión.</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="h-[220px] w-full min-w-0 sm:h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="cliFactG" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#34d399" stopOpacity={0.35} />
                          <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                      <XAxis dataKey="periodo" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
                      <YAxis
                        tick={{ fill: "#a1a1aa", fontSize: 11 }}
                        tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: 8,
                        }}
                        labelStyle={{ color: "#e4e4e7" }}
                        formatter={(v) => [formatEUR(Number(v ?? 0)), "Facturado"]}
                      />
                      <Area
                        type="monotone"
                        dataKey="facturado"
                        name="Facturado"
                        stroke="#34d399"
                        fill="url(#cliFactG)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Activity table */}
            <div className="lg:col-span-7">
              <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
                <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
                  <h2 className="text-sm font-semibold text-zinc-100">Últimos portes</h2>
                  <span className="text-xs font-medium text-zinc-500">Hasta 10 operaciones recientes</span>
                </div>
                <div className="w-full overflow-x-auto">
                  <table className="w-full min-w-0 text-left text-sm md:min-w-[640px]">
                    <thead>
                      <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                        <th className="px-5 py-3 font-semibold">Origen</th>
                        <th className="px-5 py-3 font-semibold">Destino</th>
                        <th className="hidden px-5 py-3 font-semibold sm:table-cell">Fecha</th>
                        <th className="px-5 py-3 font-semibold">Estado</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900">
                      {data.portes_recientes.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-5 py-10 text-center text-zinc-500">
                            No hay portes asociados a este cliente todavía.
                          </td>
                        </tr>
                      ) : (
                        data.portes_recientes.map((row) => (
                          <tr key={row.id} className="transition-colors hover:bg-zinc-800/30">
                            <td className="max-w-[min(100vw,12rem)] px-5 py-3">
                              <div className="truncate text-zinc-200" title={row.origen}>
                                {row.origen || "—"}
                              </div>
                            </td>
                            <td className="max-w-[min(100vw,12rem)] px-5 py-3">
                              <div className="truncate text-zinc-300" title={row.destino}>
                                {row.destino || "—"}
                              </div>
                            </td>
                            <td className="hidden px-5 py-3 text-zinc-400 sm:table-cell">
                              {formatDateShort(row.fecha_entrega_real || row.fecha)}
                            </td>
                            <td className="px-5 py-3">
                              <span className="rounded-md border border-zinc-700 bg-zinc-950/60 px-2 py-0.5 text-xs text-zinc-300">
                                {row.estado || "—"}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function ClienteDetailPage() {
  return (
    <AppShell active="clientes">
      <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
        <ClienteDetailContent />
      </RoleGuard>
    </AppShell>
  );
}
