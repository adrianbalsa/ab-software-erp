"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import type { ScatterShapeProps } from "recharts/types/util/ScatterUtils";
import { CalendarClock, CalendarDays, Gauge, Leaf, Loader2, Target } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useChartPerformance } from "@/hooks/useChartPerformance";
import {
  api,
  type BiDashboardSummary,
  type BiEsgImpactCharts,
  type BiProfitabilityCharts,
  type BiProfitabilityPoint,
  type BiTreemapNode,
} from "@/lib/api";
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

type ScatterDatum = BiProfitabilityPoint & { eta: number };

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

  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill={fill}
      fillOpacity={vampire ? 0.92 : 0.85}
      stroke={vampire ? "rgba(244, 63, 94, 0.55)" : eta > 1.2 ? "rgba(16, 185, 129, 0.45)" : "rgba(161, 161, 170, 0.45)"}
      strokeWidth={vampire ? 1.25 : 1}
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
  payload?: { margen_estimado?: number; size?: number; porte_id?: string };
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
  const label = String(name ?? "").trim();
  const short = label.length > 18 ? `${label.slice(0, 16)}…` : label;

  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} fillOpacity={0.92} stroke="#18181b" strokeWidth={1} rx={2} />
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
  const d = payload[0]?.payload;
  if (!d) return null;
  const vampire = isVampireEta(d.eta);
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
        {vampire ? (
          <span className="rounded-full border border-rose-500/80 bg-rose-950/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-200">
            Crítico — vampiro
          </span>
        ) : null}
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
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">Margen est.</dt>
          <dd className="font-medium text-emerald-400">{fmtEur(d.margin_eur)}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt className="text-zinc-500">η (precio / km·0,62)</dt>
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
  const p = payload[0]?.payload;
  if (!p) return null;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 p-3 text-xs shadow-lg backdrop-blur-sm">
      <p className="font-semibold text-zinc-100">{p.name}</p>
      <p className="mt-1 text-zinc-400">
        CO₂: <span className="text-rose-300">{fmtDec(p.size, 2)} kg</span>
      </p>
      <p className="text-zinc-400">
        Margen est.: <span className="text-emerald-400">{fmtEur(p.margen_estimado ?? 0)}</span>
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

  const [summary, setSummary] = useState<BiDashboardSummary | null>(null);
  const [profit, setProfit] = useState<BiProfitabilityCharts | null>(null);
  const [esg, setEsg] = useState<BiEsgImpactCharts | null>(null);
  const [loadSummary, setLoadSummary] = useState(true);
  const [loadProfit, setLoadProfit] = useState(true);
  const [loadEsg, setLoadEsg] = useState(true);
  const [isSyncing, setIsSyncing] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const from = toDateOnlyLocal(dateRange.from);
    const to = toDateOnlyLocal(dateRange.to);
    setErr(null);
    setIsSyncing(true);
    setLoadSummary(true);
    setLoadProfit(true);
    setLoadEsg(true);
    void (async () => {
      try {
        const [s, p, e] = await Promise.all([
          api.bi.summary(from, to),
          api.bi.profitability(from, to),
          api.bi.esgImpact(from, to),
        ]);
        if (!cancelled) {
          setSummary(s);
          setProfit(p);
          setEsg(e);
        }
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Error al cargar datos BI");
      } finally {
        if (!cancelled) {
          setLoadSummary(false);
          setLoadProfit(false);
          setLoadEsg(false);
          setIsSyncing(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rangeKey]);

  const costeKm = profit?.coste_operativo_eur_km ?? 0.62;

  const scatterData: ScatterDatum[] = useMemo(() => {
    if (!profit?.points?.length) return [];
    return profit.points.map((p) => ({
      ...p,
      eta: efficiencyEta(p, costeKm),
    }));
  }, [profit, costeKm]);

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
                DSO real, eficiencia por trayecto (η = precio / km·0,62) y huella vs margen — filtrado por periodo.
              </p>
            </div>
            <BiDateRangePicker dateRange={dateRange} onChange={setDateRange} isSyncing={isSyncing} />
          </header>

          <div className="mx-auto grid w-full max-w-[1600px] flex-1 gap-6 p-4 sm:p-6">
            {err ? (
              <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 px-4 py-3 text-sm text-rose-200">{err}</div>
            ) : null}

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
                      <p className="mt-1 text-xs text-zinc-500">ratio precio / (km × 0,62)</p>
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

            {/* Scatter */}
            <Card className="bunker-card overflow-hidden border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Rentabilidad por trayecto</CardTitle>
                <CardDescription className="text-zinc-400">
                  Cada punto es un porte completado. Color: η &lt; 1 en rosa, η &gt; 1,2 en esmeralda (η = precio / (km × 0,62)).
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
                        name="Margen"
                        width={isNarrow ? 56 : 72}
                        tick={{ fill: "#a1a1aa", fontSize: axisTick }}
                        tickFormatter={(v) => fmtEur(Number(v))}
                        label={{
                          value: "Margen (EUR)",
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
                  Superficie ∝ CO₂ emitido (kg). Color ∝ rentabilidad estimada (margen EUR).
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
