"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ESGImpactCard } from "@/components/bi/ESGImpactCard";
import { MarginWaterfallChart } from "@/components/bi/MarginWaterfallChart";
import { PortalClienteAlert } from "@/components/portal-cliente/PortalClienteAlert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { fetchPortalProfitMarginAnalytics, type ProfitMarginAnalytics } from "@/lib/api";

function toDateOnlyLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseDateOnlyLocal(s: string): Date {
  const [y, m, d] = s.split("-").map((x) => parseInt(x, 10));
  return new Date(y || 1970, (m || 1) - 1, d || 1, 12, 0, 0, 0);
}

function defaultRange(): { from: Date; to: Date } {
  const to = new Date();
  to.setHours(12, 0, 0, 0);
  const from = new Date(to);
  from.setMonth(from.getMonth() - 5);
  return { from, to };
}

const fmtEur = (n: number) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 }).format(n);

export default function PortalClienteAnalyticsPage() {
  const { catalog } = useOptionalLocaleCatalog();
  const p = catalog.pages.portalClienteBi;
  const [dateRange, setDateRange] = useState(defaultRange);
  const [granularity, setGranularity] = useState<"month" | "week">("month");
  const [vehiculoFilter, setVehiculoFilter] = useState("");
  const [data, setData] = useState<ProfitMarginAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const rangeKey = `${toDateOnlyLocal(dateRange.from)}|${toDateOnlyLocal(dateRange.to)}`;
  const fetchKey = `${rangeKey}|${granularity}|${vehiculoFilter.trim()}`;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    void (async () => {
      try {
        const res = await fetchPortalProfitMarginAnalytics({
          from: toDateOnlyLocal(dateRange.from),
          to: toDateOnlyLocal(dateRange.to),
          granularity,
          vehiculo_id: vehiculoFilter.trim() || undefined,
        });
        if (!cancelled) setData(res);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : p.errLoad);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchKey, p.errLoad]); // eslint-disable-line react-hooks/exhaustive-deps -- fetchKey consolida rango y filtros

  const marginTrendData = useMemo(() => {
    if (!data?.series?.length) return [];
    return data.series.map((r) => ({
      label: r.period_label,
      Ingresos: r.ingresos_totales,
      Combustible: r.gastos_combustible,
      Peajes: r.gastos_peajes,
      Otros: r.gastos_otros,
    }));
  }, [data]);

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{p.title}</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{p.subtitle}</p>
      </div>

      {err ? <PortalClienteAlert>{err}</PortalClienteAlert> : null}

      <Card className="border-zinc-200/90 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900/40">
        <CardHeader>
          <CardTitle className="text-lg text-zinc-900 dark:text-zinc-50">{p.periodLabel}</CardTitle>
          <CardDescription className="dark:text-zinc-400">{p.granularityLabel}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
            Desde
            <Input
              type="date"
              value={toDateOnlyLocal(dateRange.from)}
              onChange={(e) => setDateRange((r) => ({ ...r, from: parseDateOnlyLocal(e.target.value) }))}
              className="dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
            Hasta
            <Input
              type="date"
              value={toDateOnlyLocal(dateRange.to)}
              onChange={(e) => setDateRange((r) => ({ ...r, to: parseDateOnlyLocal(e.target.value) }))}
              className="dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
            {p.granularityLabel}
            <select
              className="h-10 rounded-md border border-zinc-200 bg-white px-2 text-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              value={granularity}
              onChange={(e) => setGranularity(e.target.value === "week" ? "week" : "month")}
              aria-label={p.granularityLabel}
            >
              <option value="month">{p.month}</option>
              <option value="week">{p.week}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-zinc-600 dark:text-zinc-400">
            {p.vehiculoLabel}
            <Input
              value={vehiculoFilter}
              onChange={(e) => setVehiculoFilter(e.target.value)}
              placeholder={p.vehiculoPlaceholder}
              className="dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              aria-label={p.vehiculoLabel}
              autoComplete="off"
            />
          </label>
        </CardContent>
      </Card>

      {loading ? (
        <p className="text-sm text-zinc-500" role="status" aria-live="polite">
          {p.loading}
        </p>
      ) : data ? (
        <div className="space-y-8">
          <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 sm:p-6">
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <MarginWaterfallChart
                analytics={data}
                title={p.waterfallTitle}
                csvFilename={`portal-profit-margin_${toDateOnlyLocal(dateRange.from)}_${toDateOnlyLocal(dateRange.to)}.csv`}
              />
              <ESGImpactCard esg={data.esg_month_over_month} title={p.esgTitle} />
            </div>
          </div>

          {marginTrendData.length ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4 sm:p-6">
              <Card className="border-zinc-800 bg-transparent shadow-none">
                <CardHeader>
                  <CardTitle className="text-lg text-zinc-50">{p.trendTitle}</CardTitle>
                  <CardDescription className="text-zinc-400">{p.trendDesc}</CardDescription>
                </CardHeader>
                <CardContent className="h-[min(45vh,360px)] min-h-[260px] w-full">
                  <div role="img" aria-label={p.trendTitle} className="h-full w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={marginTrendData} margin={{ top: 8, right: 8, left: 4, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 10 }} interval={0} angle={-14} height={52} />
                        <YAxis
                          tickFormatter={(v) => fmtEur(Number(v))}
                          width={72}
                          tick={{ fill: "#a1a1aa", fontSize: 11 }}
                        />
                        <Tooltip
                          contentStyle={{ background: "#09090b", border: "1px solid #3f3f46" }}
                          formatter={(v) => fmtEur(Number(v ?? 0))}
                        />
                        <Legend wrapperStyle={{ color: "#d4d4d8", fontSize: 12 }} />
                        <Bar dataKey="Combustible" stackId="g" fill="#f59e0b" />
                        <Bar dataKey="Peajes" stackId="g" fill="#38bdf8" />
                        <Bar dataKey="Otros" stackId="g" fill="#a78bfa" />
                        <Line type="monotone" dataKey="Ingresos" stroke="#10b981" strokeWidth={2} dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </div>
      ) : (
        <Button type="button" variant="outline" onClick={() => window.location.reload()}>
          Reintentar
        </Button>
      )}
    </div>
  );
}
