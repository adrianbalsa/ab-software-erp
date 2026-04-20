"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import type { ScatterShapeProps } from "recharts/types/util/ScatterUtils";
import { CalendarClock, CalendarDays, Gauge, Info, Leaf, Loader2, Target, TrendingUp, Zap } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { ESGImpactCard } from "@/components/bi/ESGImpactCard";
import { MarginWaterfallChart } from "@/components/bi/MarginWaterfallChart";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useChartPerformance } from "@/hooks/useChartPerformance";
import {
  api,
  getAdvancedMetrics,
  type AdvancedMetricsResponse,
  type BiDashboardSummary,
  type BiEsgImpactCharts,
  type BiProfitabilityCharts,
  type BiProfitabilityPoint,
  type BiTreemapNode,
  type ProfitMarginAnalytics,
} from "@/lib/api";
import { publicOperationalCostEurKmDefault } from "@/lib/operationalPricing";
import { cn } from "@/lib/utils";

const fmtInt = (n: number | null | undefined) =>
  n == null || Number.isNaN(n)
    ? "—"
    : new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 }).format(n);

const fmtDec = (n: number | null | undefined, digits = 2) =>
  n == null || Number.isNaN(n)
    ? "—"
    : new Intl.NumberFormat("es-ES", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(n);

const fmtEur = (n: number | null | undefined) =>
  n == null || Number.isNaN(n)
    ? "—"
    : new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(n);

/** Fecha local YYYY-MM-DD (evita desfases TZ al usar input type=date). */
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

function defaultBiDateRange(): { from: Date; to: Date } {
  const to = new Date();
  to.setHours(12, 0, 0, 0);
  const from = new Date(to);
  from.setDate(from.getDate() - 29);
  return { from, to };
}

function formatPeriodLabel(from: Date, to: Date): string {
  const fmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric" });
  return `${fmt.format(from)} – ${fmt.format(to)}`;
}

type ScatterDatum = BiProfitabilityPoint & { eta: number; coste_operativo_eur_km: number };

function efficiencyEta(p: BiProfitabilityPoint, costeKm: number): number {
  const precio = p.precio_pactado ?? 0;
  const denom = p.km * costeKm;
  if (denom <= 1e-9) return 0;
  return precio / denom;
}

function scatterFill(eta: number): string {
  if (eta < 1) return "#f43f5e"; // rose-500
  if (eta > 1.2) return "#10b981"; // emerald-500
  return "#a1a1aa"; // zinc-400
}

/** η &lt; 1: trayecto por debajo del umbral — “vampiro” de rentabilidad en este gráfico. */
function isVampireEta(eta: number): boolean {
  return eta < 1;
}

function ProfitabilityScatterDot(props: ScatterShapeProps) {
  const { cx, cy, width, height, payload } = props;
  const datum = payload as ScatterDatum | undefined;
  if (cx == null || cy == null || datum == null) return null;
  const eta = datum.eta;
  const fill = scatterFill(eta);
  const size = Number(width ?? height ?? 10);
  const r = Number.isFinite(size) && size > 0 ? Math.max(4, Math.min(9, size / 2)) : 5.5;
  const vampire = isVampireEta(eta);
  const estimated = datum.estimated_margin === true;

  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill={fill}
      fillOpacity={estimated ? 0.65 : vampire ? 0.92 : 0.85}
      stroke={vampire ? "rgba(244, 63, 94, 0.55)" : eta > 1.2 ? "rgba(16, 185, 129, 0.45)" : "rgba(161, 161, 170, 0.45)"}
      strokeWidth={estimated ? 1.4 : vampire ? 1.25 : 1}
      strokeDasharray={estimated ? "4 3" : undefined}
      className={vampire ? "bi-scatter-vampire-dot" : undefined}
    />
  );
}

function marginHue(m: number, minM: number, maxM: number): string {
  if (maxM <= minM) return "hsl(220 14% 38%)";
  const t = Math.min(1, Math.max(0, (m - minM) / (maxM - minM)));
  const hue = 350 - 205 * t;
  return `hsl(${hue} 62% 42%)`;
}

type TreemapCellProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  depth?: number;
  name?: string;
  payload?: { margen_estimado?: number; size?: number; porte_id?: string; estimated_fallback?: boolean };
  minMargen: number;
  maxMargen: number;
};

function BiTreemapCell({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  name,
  payload,
  minMargen,
  maxMargen,
}: TreemapCellProps) {
  if (width < 2 || height < 2) return null;
  const m = Number(payload?.margen_estimado ?? 0);
  const fill = marginHue(m, minMargen, maxMargen);
  const est = payload?.estimated_fallback === true;
  const label = String(name ?? "").trim();
  const short = label.length > 18 ? `${label.slice(0, 16)}…` : label;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        fillOpacity={est ? 0.72 : 0.92}
        stroke="#18181b"
        strokeWidth={est ? 1.5 : 1}
        strokeDasharray={est ? "5 4" : undefined}
        rx={2}
      />
      {width > 52 && height > 20 ? (
        <text
          x={x + 4}
          y={y + 14}
          fill="#fafafa"
          fontSize={10}
          fontWeight={600}
          style={{ textShadow: "0 1px 2px rgb(0 0 0 / 0.8)" }}
        >
          {short}
        </text>
      ) : null}
    </g>
  );
}

function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex min-h-[420px] w-full animate-pulse flex-col gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6",
        className,
      )}
    >
      <div className="h-4 w-1/3 rounded bg-zinc-800" />
      <div className="mt-4 flex-1 rounded-lg bg-zinc-800/60" />
      <div className="flex gap-2">
        <div className="h-3 flex-1 rounded bg-zinc-800/80" />
        <div className="h-3 flex-1 rounded bg-zinc-800/80" />
      </div>
    </div>
  );
}

function KpiSkeleton() {
  return (
    <div className="h-[120px] animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
      <div className="h-3 w-24 rounded bg-zinc-800" />
      <div className="mt-6 h-8 w-20 rounded bg-zinc-800" />
    </div>
  );
}

type ScatterTooltipProps = {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: ScatterDatum }>;
};

function ProfitabilityTooltip({ active, payload }: ScatterTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ScatterDatum | undefined;
  if (!d) return null;
  const vampire = isVampireEta(d.eta);
  const estimated = d.estimated_margin === true;
  const precio = d.precio_pactado ?? 0;
  const km = d.km ?? 0;
  const ck = d.coste_operativo_eur_km ?? publicOperationalCostEurKmDefault();
  const costeEstimadoKm = km * ck;
  const fuel = d.allocated_fuel_eur;
  const other = d.other_opex_eur;
  const tieneReal = !estimated && other != null;

  return (
    <div
      className={cn(
        "max-w-sm rounded-lg bg-zinc-950/95 p-4 text-sm shadow-xl shadow-black/40 backdrop-blur-sm",
        vampire
          ? "border-2 border-rose-500 ring-2 ring-rose-500/25"
          : "border border-zinc-700",
      )}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
        <p className="font-semibold text-zinc-100">Porte</p>
        <div className="flex flex-wrap items-center gap-1.5">
          {estimated ? (
            <span className="rounded-full border border-amber-500/70 bg-amber-950/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
              Estimado
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1 rounded-full border border-emerald-500/50 bg-emerald-950/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200"
              title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
            >
              P&amp;L real
              <Info className="size-3 shrink-0 text-emerald-400/90" aria-hidden />
            </span>
          )}
          {vampire ? (
            <span className="rounded-full border border-rose-500/80 bg-rose-950/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-200">
              Crítico — vampiro
            </span>
          ) : null}
        </div>
      </div>
      <dl className="space-y-1.5 text-zinc-300">
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">ID</dt>
          <dd className="font-mono text-xs text-zinc-200">{d.porte_id}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">Cliente</dt>
          <dd className="text-right text-zinc-100">{d.cliente?.trim() || "—"}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">Vehículo</dt>
          <dd className="text-right text-zinc-100">{d.vehiculo?.trim() || "—"}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">Distancia</dt>
          <dd>{fmtDec(d.km, 1)} km</dd>
        </div>
        <div className="border-t border-zinc-800 pt-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">Desglose coste</p>
          <div className="flex justify-between gap-6">
            <dt className="text-zinc-500">Ingreso</dt>
            <dd className="text-zinc-100">{fmtEur(precio)}</dd>
          </div>
          {tieneReal ? (
            <>
              <div className="flex justify-between gap-6">
                <dt className="text-zinc-500">Combustible real</dt>
                <dd className="text-amber-200">− {fmtEur(fuel ?? 0)}</dd>
              </div>
              <div className="flex justify-between gap-6">
                <dt className="text-zinc-500">Otros costes</dt>
                <dd className="text-sky-200">− {fmtEur(other)}</dd>
              </div>
            </>
          ) : (
            <div className="flex justify-between gap-6">
              <dt className="text-zinc-500">Coste operativo est. (km×{fmtDec(ck, 2)})</dt>
              <dd className="text-amber-200">− {fmtEur(costeEstimadoKm)}</dd>
            </div>
          )}
        </div>
        <div className="flex justify-between gap-6 border-t border-zinc-800 pt-2">
          <dt className="text-zinc-500">Margen P&amp;L {estimated ? "(proxy)" : "real"}</dt>
          <dd className="font-medium text-emerald-400">{fmtEur(d.margin_eur)}</dd>
        </div>
        {d.margin_estimado_legacy_eur != null && !estimated ? (
          <div className="flex justify-between gap-6 text-[11px] text-zinc-500">
            <dt>Referencia legacy (km×coste)</dt>
            <dd>{fmtEur(d.margin_estimado_legacy_eur)}</dd>
          </div>
        ) : null}
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">η (precio / km·coste)</dt>
          <dd className="font-mono text-zinc-100">{fmtDec(d.eta, 2)}</dd>
        </div>
      </dl>
    </div>
  );
}

type TreemapTooltipProps = {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: { name?: string; size?: number; margen_estimado?: number; porte_id?: string } }>;
};

function TreemapBizTooltip({ active, payload }: TreemapTooltipProps) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload as {
    name?: string;
    size?: number;
    margen_estimado?: number;
    porte_id?: string;
    estimated_fallback?: boolean;
  };
  if (!p) return null;
  const est = p.estimated_fallback === true;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 p-3 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-semibold text-zinc-100">{p.name}</p>
      {est ? (
        <p className="mt-1 text-amber-300/90">Margen proxy (sin ticket combustible vinculado)</p>
      ) : (
        <p className="mt-0.5 inline-flex items-center gap-1 text-[10px] text-emerald-400/90">
          <Info className="size-3" aria-hidden />
          P&amp;L con combustible real imputado
        </p>
      )}
      <p className="mt-1 text-zinc-400">
        CO₂: <span className="text-rose-300">{fmtDec(p.size, 2)} kg</span>
      </p>
      <p className="text-zinc-400">
        Margen: <span className="text-emerald-400">{fmtEur(p.margen_estimado ?? 0)}</span>
      </p>
      {p.porte_id ? (
        <p className="mt-1 font-mono text-[10px] text-zinc-500">{p.porte_id}</p>
      ) : null}
    </div>
  );
}

type BiDateRangePickerProps = {
  dateRange: { from: Date; to: Date };
  onChange: (next: { from: Date; to: Date }) => void;
  isSyncing: boolean;
};

function BiDateRangePicker({ dateRange, onChange, isSyncing }: BiDateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (ev: MouseEvent) => {
      if (ref.current && !ref.current.contains(ev.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative shrink-0" ref={ref}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen((o) => !o)}
        className="h-9 gap-2 border-zinc-700 bg-zinc-900/80 text-zinc-100 hover:bg-zinc-800/90"
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <CalendarDays className="size-4 shrink-0 text-emerald-400" aria-hidden />
        <span className="hidden max-w-[200px] truncate text-left sm:inline md:max-w-[280px]">
          {formatPeriodLabel(dateRange.from, dateRange.to)}
        </span>
        <span className="sm:hidden">Periodo</span>
        {isSyncing ? <Loader2 className="size-4 shrink-0 animate-spin text-amber-400" aria-label="Sincronizando" /> : null}
      </Button>
      {open ? (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-[min(calc(100vw-2rem),20rem)] rounded-xl border border-zinc-700 bg-zinc-900 p-4 shadow-2xl shadow-black/50 ring-1 ring-white/5"
          role="dialog"
          aria-label="Seleccionar rango de fechas"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Periodo (fecha porte)</p>
          <p className="mt-1 text-[11px] leading-snug text-zinc-500">
            KPIs y gráficos usan portes cuya <strong className="text-zinc-400">fecha</strong> cae en el rango. DSO usa
            facturas emitidas en el mismo rango.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="block text-xs text-zinc-400">
              Desde
              <input
                type="date"
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-2 text-sm text-zinc-100 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                value={toDateOnlyLocal(dateRange.from)}
                onChange={(e) => onChange({ ...dateRange, from: parseDateOnlyLocal(e.target.value) })}
              />
            </label>
            <label className="block text-xs text-zinc-400">
              Hasta
              <input
                type="date"
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-2 text-sm text-zinc-100 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                value={toDateOnlyLocal(dateRange.to)}
                onChange={(e) => onChange({ ...dateRange, to: parseDateOnlyLocal(e.target.value) })}
              />
            </label>
          </div>
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-zinc-800 pt-3">
            <span className={cn("text-xs", isSyncing ? "text-amber-400/90" : "text-zinc-600")}>
              {isSyncing ? "Sincronizando datos…" : "Listo"}
            </span>
            <Button type="button" variant="ghost" size="sm" className="h-8 text-xs text-zinc-400" onClick={() => setOpen(false)}>
              Cerrar
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function BiDashboardPage() {
  const { staticCharts, isNarrow } = useChartPerformance();
  const axisTick = isNarrow ? 10 : 12;

  const [dateRange, setDateRange] = useState(defaultBiDateRange);
  const rangeKey = `${toDateOnlyLocal(dateRange.from)}|${toDateOnlyLocal(dateRange.to)}`;

  const [granularity, setGranularity] = useState<"month" | "week">("month");
  const [vehiculoFilter, setVehiculoFilter] = useState("");
  const [clienteFilter, setClienteFilter] = useState("");

  const [summary, setSummary] = useState<BiDashboardSummary | null>(null);
  const [profit, setProfit] = useState<BiProfitabilityCharts | null>(null);
  const [esg, setEsg] = useState<BiEsgImpactCharts | null>(null);
  const [advancedMetrics, setAdvancedMetrics] = useState<AdvancedMetricsResponse | null>(null);
  const [profitMargin, setProfitMargin] = useState<ProfitMarginAnalytics | null>(null);
  const [loadSummary, setLoadSummary] = useState(true);
  const [loadProfit, setLoadProfit] = useState(true);
  const [loadEsg, setLoadEsg] = useState(true);
  const [loadPm, setLoadPm] = useState(true);
  const [isSyncing, setIsSyncing] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const pmKey = `${rangeKey}|${granularity}|${vehiculoFilter.trim()}|${clienteFilter.trim()}`;

  useEffect(() => {
    let cancelled = false;
    const from = toDateOnlyLocal(dateRange.from);
    const to = toDateOnlyLocal(dateRange.to);
    setErr(null);
    setIsSyncing(true);
    setLoadSummary(true);
    setLoadProfit(true);
    setLoadEsg(true);
    setLoadPm(true);
    void (async () => {
      try {
        const [s, p, e, adv, pm] = await Promise.all([
          api.bi.summary(from, to),
          api.bi.profitability(from, to),
          api.bi.esgImpact(from, to),
          getAdvancedMetrics().catch(() => null),
          api.analytics
            .profitMargin({
              from,
              to,
              granularity,
              vehiculo_id: vehiculoFilter.trim() || undefined,
              cliente_id: clienteFilter.trim() || undefined,
            })
            .catch(() => null),
        ]);
        if (!cancelled) {
          setSummary(s);
          setProfit(p);
          setEsg(e);
          setAdvancedMetrics(adv);
          setProfitMargin(pm);
        }
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Error al cargar datos BI");
      } finally {
        if (!cancelled) {
          setLoadSummary(false);
          setLoadProfit(false);
          setLoadEsg(false);
          setLoadPm(false);
          setIsSyncing(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pmKey]); // eslint-disable-line react-hooks/exhaustive-deps -- pmKey consolida rango y filtros

  const costeKm = profit?.coste_operativo_eur_km ?? publicOperationalCostEurKmDefault();

  const scatterData: ScatterDatum[] = useMemo(() => {
    if (!profit?.points?.length) return [];
    return profit.points.map((p) => ({
      ...p,
      eta: efficiencyEta(p, costeKm),
      coste_operativo_eur_km: costeKm,
    }));
  }, [profit, costeKm]);

  const marginTrendData = useMemo(() => {
    if (!profitMargin?.series?.length) return [];
    return profitMargin.series.map((r) => ({
      label: r.period_label,
      Ingresos: r.ingresos_totales,
      Combustible: r.gastos_combustible,
      Peajes: r.gastos_peajes,
      Otros: r.gastos_otros,
    }));
  }, [profitMargin]);

  const { treemapLeaves, margenMin, margenMax } = useMemo(() => {
    const nodes = esg?.treemap_nodes ?? [];
    const margens = nodes.map((n) => Number(n.margen_estimado ?? 0));
    const minM = margens.length ? Math.min(...margens) : 0;
    const maxM = margens.length ? Math.max(...margens) : 1;
    const leaves = nodes.map((n: BiTreemapNode) => ({
      name: n.name || "—",
      size: Math.max(Number(n.size) || 0, 1e-4),
      margen_estimado: n.margen_estimado ?? 0,
      porte_id: n.porte_id ?? undefined,
      estimated_fallback: n.estimated_fallback === true,
    }));
    return {
      treemapLeaves: leaves,
      margenMin: minM,
      margenMax: maxM === minM ? minM + 1 : maxM,
    };
  }, [esg]);

  return (
    <AppShell active="bi">
      <RoleGuard
        allowedRoles={["owner", "admin"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-400">Acceso restringido: solo dirección.</p>
          </main>
        }
      >
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
          <header className="flex min-h-16 shrink-0 flex-col gap-3 border-b border-zinc-800 bg-zinc-950/90 px-4 py-3 backdrop-blur-md sm:flex-row sm:items-start sm:justify-between sm:px-6 sm:py-3">
            <div className="min-w-0 flex-1">
              <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-zinc-100 sm:text-2xl">
                <Target className="h-6 w-6 shrink-0 text-emerald-500 sm:h-7 sm:w-7" aria-hidden />
                Inteligencia de negocio
              </h1>
              <p className="mt-0.5 text-xs text-zinc-400 sm:text-sm">
                DSO real, eficiencia por trayecto (η = precio / (km × {fmtDec(costeKm, 2)} €)) y huella vs margen —
                filtrado por periodo.
              </p>
            </div>
            <BiDateRangePicker dateRange={dateRange} onChange={setDateRange} isSyncing={isSyncing} />
          </header>

          <div className="border-b border-zinc-800 bg-zinc-950/80 px-4 py-3 sm:px-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Filtros BI (portes / gastos)</p>
            <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
              <label className="flex min-w-[10rem] flex-col gap-1 text-xs text-zinc-400">
                Agrupación temporal
                <select
                  className="h-9 rounded-lg border border-zinc-700 bg-zinc-950 px-2 text-sm text-zinc-100 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40"
                  value={granularity}
                  onChange={(e) => setGranularity(e.target.value === "week" ? "week" : "month")}
                  aria-label="Agrupación temporal del margen"
                >
                  <option value="month">Mes</option>
                  <option value="week">Semana (ISO)</option>
                </select>
              </label>
              <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs text-zinc-400">
                Vehículo (UUID flota)
                <Input
                  value={vehiculoFilter}
                  onChange={(e) => setVehiculoFilter(e.target.value)}
                  placeholder="Opcional"
                  className="h-9 border-zinc-700 bg-zinc-950 text-zinc-100"
                  aria-label="Filtrar por vehículo_id"
                  autoComplete="off"
                />
              </label>
              <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-xs text-zinc-400">
                Cliente (UUID)
                <Input
                  value={clienteFilter}
                  onChange={(e) => setClienteFilter(e.target.value)}
                  placeholder="Opcional"
                  className="h-9 border-zinc-700 bg-zinc-950 text-zinc-100"
                  aria-label="Filtrar por cliente_id"
                  autoComplete="off"
                />
              </label>
            </div>
          </div>

          <div className="mx-auto grid w-full max-w-[1600px] flex-1 gap-6 p-4 sm:p-6">
            {err ? (
              <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">{err}</div>
            ) : null}

            {/* Real-cost KPIs (advanced-metrics — agregado empresa, no filtrado por rango BI) */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {loadSummary ? (
                <>
                  <KpiSkeleton />
                  <KpiSkeleton />
                </>
              ) : (
                <>
                  <Card className="bunker-card border-emerald-500/20 bg-gradient-to-br from-emerald-950/35 to-zinc-950">
                    <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-sm font-medium text-zinc-200">
                          <TrendingUp className="h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
                          Índice de Margen Real
                        </CardTitle>
                        <CardDescription className="text-xs text-zinc-500">
                          Desviación agregada: margen P&amp;L con combustible imputado vs estimación km×coste.
                        </CardDescription>
                      </div>
                      <span
                        className="shrink-0 text-zinc-500"
                        title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
                      >
                        <Info className="h-5 w-5" aria-hidden />
                      </span>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tracking-tight text-zinc-50">
                        {advancedMetrics?.real_margin_index != null && !Number.isNaN(advancedMetrics.real_margin_index)
                          ? `${advancedMetrics.real_margin_index >= 0 ? "+" : ""}${fmtDec(advancedMetrics.real_margin_index, 1)} %`
                          : "—"}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">Últimos meses con portes completados vinculados.</p>
                    </CardContent>
                  </Card>
                  <Card className="bunker-card border-amber-500/20 bg-gradient-to-br from-amber-950/25 to-zinc-950">
                    <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-sm font-medium text-zinc-200">
                          <Zap className="h-5 w-5 shrink-0 text-amber-400" aria-hidden />
                          Ratio de Eficiencia de Combustible
                        </CardTitle>
                        <CardDescription className="text-xs text-zinc-500">
                          Ingresos por € de combustible real imputado (mismo universo que el índice).
                        </CardDescription>
                      </div>
                      <span
                        className="shrink-0 text-zinc-500"
                        title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
                      >
                        <Info className="h-5 w-5" aria-hidden />
                      </span>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tracking-tight text-zinc-50">
                        {advancedMetrics?.fuel_efficiency_ratio != null &&
                        !Number.isNaN(advancedMetrics.fuel_efficiency_ratio)
                          ? `${fmtDec(advancedMetrics.fuel_efficiency_ratio, 2)} € / €`
                          : "—"}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">Mayor valor: más ingreso por cada euro de gasoil cargado.</p>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {loadSummary ? (
                <>
                  <KpiSkeleton />
                  <KpiSkeleton />
                  <KpiSkeleton />
                </>
              ) : (
                <>
                  <Card className="bunker-card border-zinc-800 bg-gradient-to-br from-zinc-900/90 to-zinc-950">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-zinc-200">DSO real</CardTitle>
                      <CalendarClock className="h-5 w-5 text-sky-400" aria-hidden />
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tracking-tight text-zinc-50">{fmtDec(summary?.dso_days, 1)}</p>
                      <p className="mt-1 text-xs text-zinc-500">días (emisión → cobro bancario)</p>
                      <p className="mt-2 text-[11px] text-zinc-600">Muestra: {fmtInt(summary?.dso_sample_size)} facturas</p>
                    </CardContent>
                  </Card>
                  <Card className="bunker-card border-zinc-800 bg-gradient-to-br from-zinc-900/90 to-zinc-950">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-zinc-200">Eficiencia media</CardTitle>
                      <Gauge className="h-5 w-5 text-amber-400" aria-hidden />
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tracking-tight text-zinc-50">{fmtDec(summary?.avg_efficiency_eur_per_eur_km, 2)}</p>
                      <p className="mt-1 text-xs text-zinc-500">ratio precio / (km × {fmtDec(costeKm, 2)} €)</p>
                      <p className="mt-2 text-[11px] text-zinc-600">n = {fmtInt(summary?.efficiency_sample_size)} portes</p>
                    </CardContent>
                  </Card>
                  <Card className="bunker-card border-zinc-800 bg-gradient-to-br from-zinc-900/90 to-zinc-950">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium text-zinc-200">CO₂ ahorrado</CardTitle>
                      <Leaf className="h-5 w-5 text-emerald-400" aria-hidden />
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold tracking-tight text-zinc-50">
                        {summary?.total_co2_saved_kg != null ? fmtDec(summary.total_co2_saved_kg, 1) : "—"}
                      </p>
                      <p className="mt-1 text-xs text-zinc-500">kg vs línea base Euro III</p>
                      <p className="mt-2 text-[11px] text-zinc-600">Portes con dato: {fmtInt(summary?.co2_saved_portes)}</p>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>

            {/* Margen + ESG (analytics API) */}
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {loadPm ? (
                <>
                  <ChartSkeleton className="min-h-[280px]" />
                  <ChartSkeleton className="min-h-[280px]" />
                </>
              ) : profitMargin ? (
                <>
                  <MarginWaterfallChart
                    analytics={profitMargin}
                    csvFilename={`profit-margin_${toDateOnlyLocal(dateRange.from)}_${toDateOnlyLocal(dateRange.to)}.csv`}
                  />
                  <ESGImpactCard esg={profitMargin.esg_month_over_month} />
                </>
              ) : (
                <div className="col-span-full rounded-lg border border-dashed border-zinc-800 bg-zinc-900/30 px-4 py-6 text-sm text-zinc-500">
                  No se pudieron cargar los agregados de margen (compruebe permisos o inténtelo de nuevo).
                </div>
              )}
            </div>

            {loadPm || !profitMargin?.series?.length ? null : (
              <Card className="bunker-card overflow-hidden border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-zinc-100">Serie temporal — ingresos vs gastos</CardTitle>
                  <CardDescription className="text-zinc-400">
                    Barras apiladas: combustible, peajes y otros. Línea: ingresos de portes (mismo rango y filtros).
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-[min(50vh,380px)] min-h-[280px] w-full p-2 sm:p-4">
                  <div
                    role="img"
                    aria-label="Gráfico combinado de ingresos y gastos apilados por periodo"
                    className="h-full w-full"
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={marginTrendData} margin={{ top: 8, right: 8, left: 4, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 10 }} interval={0} angle={-16} height={56} />
                        <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickFormatter={(v) => fmtEur(Number(v))} width={76} />
                        <Tooltip formatter={(v) => fmtEur(Number(v ?? 0))} />
                        <Legend wrapperStyle={{ color: "#d4d4d8", fontSize: 12 }} />
                        <Bar dataKey="Combustible" stackId="g" fill="#f59e0b" isAnimationActive={!staticCharts} />
                        <Bar dataKey="Peajes" stackId="g" fill="#38bdf8" isAnimationActive={!staticCharts} />
                        <Bar dataKey="Otros" stackId="g" fill="#a78bfa" isAnimationActive={!staticCharts} />
                        <Line
                          type="monotone"
                          dataKey="Ingresos"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                          isAnimationActive={!staticCharts}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Scatter */}
            <Card className="bunker-card overflow-hidden border-zinc-800">
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2 text-zinc-100">
                  Rentabilidad por trayecto
                  <span
                    className="inline-flex text-zinc-500"
                    title="Cálculo basado en tickets de combustible reales vinculados a este vehículo/fecha"
                  >
                    <Info className="size-4" aria-hidden />
                  </span>
                </CardTitle>
                <CardDescription className="text-zinc-400">
                  Eje Y: margen P&amp;L real (EUR) cuando hay combustible imputado; borde discontinuo = estimación (sin ticket).
                  Color η: precio / (km × coste) — &lt; 1 rosa, &gt; 1,2 esmeralda.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[min(70vh,560px)] min-h-[420px] w-full p-2 sm:p-4">
                {loadProfit ? (
                  <ChartSkeleton className="min-h-[420px]" />
                ) : scatterData.length === 0 ? (
                  <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-900/30 text-sm text-zinc-500">
                    No hay portes completados con km &gt; 0 para mostrar.
                  </div>
                ) : (
                  <>
                    <style>{`
                      @keyframes bi-vampire-glow {
                        0%, 100% { opacity: 1; filter: drop-shadow(0 0 6px rgba(244, 63, 94, 0.9)); }
                        50% { opacity: 0.78; filter: drop-shadow(0 0 11px rgba(244, 63, 94, 0.95)); }
                      }
                      .bi-scatter-vampire-dot {
                        animation: bi-vampire-glow 2.4s ease-in-out infinite;
                      }
                    `}</style>
                    <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 16, right: 20, bottom: 16, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                      <XAxis
                        type="number"
                        dataKey="km"
                        name="Km"
                        tick={{ fill: "#a1a1aa", fontSize: axisTick }}
                        tickFormatter={(v) => `${fmtDec(Number(v), 0)} km`}
                        label={{ value: "Distancia (km)", position: "bottom", offset: 0, fill: "#71717a", fontSize: 12 }}
                      />
                      <YAxis
                        type="number"
                        dataKey="margin_eur"
                        name="Margen P&L real"
                        width={isNarrow ? 56 : 80}
                        tick={{ fill: "#a1a1aa", fontSize: axisTick }}
                        tickFormatter={(v) => fmtEur(Number(v))}
                        label={{
                          value: "Margen P&L real (EUR)",
                          angle: -90,
                          position: "insideLeft",
                          fill: "#71717a",
                          fontSize: 12,
                        }}
                      />
                      <Tooltip content={<ProfitabilityTooltip />} cursor={{ strokeDasharray: "3 3", stroke: "#71717a" }} />
                      <Scatter
                        name="Portes"
                        data={scatterData}
                        isAnimationActive={!staticCharts}
                        shape={(dotProps: ScatterShapeProps) => <ProfitabilityScatterDot {...dotProps} />}
                      />
                    </ScatterChart>
                    </ResponsiveContainer>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Treemap */}
            <Card className="bunker-card overflow-hidden border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Impacto de carbono vs margen</CardTitle>
                <CardDescription className="text-zinc-400">
                  Superficie ∝ CO₂ (kg). Color ∝ margen P&amp;L (real o proxy). Borde discontinuo: sin ticket de combustible
                  vinculado.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-[min(65vh,520px)] min-h-[400px] w-full p-2 sm:p-4">
                {loadEsg ? (
                  <ChartSkeleton className="min-h-[400px]" />
                ) : treemapLeaves.length === 0 ? (
                  <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-900/30 text-sm text-zinc-500">
                    No hay datos ESG agregados para treemap.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <Treemap
                      data={treemapLeaves}
                      dataKey="size"
                      aspectRatio={4 / 3}
                      stroke="#09090b"
                      isAnimationActive={!staticCharts}
                      animationDuration={400}
                      content={(props: Record<string, unknown>) => (
                        <BiTreemapCell
                          {...(props as TreemapCellProps)}
                          minMargen={margenMin}
                          maxMargen={margenMax}
                        />
                      )}
                    >
                      <Tooltip content={<TreemapBizTooltip />} />
                    </Treemap>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
