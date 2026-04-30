"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { Download, FileDown, Loader2 } from "lucide-react";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";

import { DashboardSkeleton } from "@/components/bi/dashboard-skeleton";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DatePickerWithRange } from "@/components/ui/date-picker-with-range";
import { useFinancialHealth, type FinancialHealthGranularity, type FinancialHealthOut } from "@/hooks/use-bi";
import { exportToCSV } from "@/lib/export-to-csv";

const currencyFormatter = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

const percentFormatter = new Intl.NumberFormat("es-ES", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function formatCurrency(value: number) {
  return currencyFormatter.format(value);
}

function toDateOnlyLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function defaultSixMonthRange() {
  const end = new Date();
  end.setHours(12, 0, 0, 0);
  const start = new Date(end);
  start.setMonth(start.getMonth() - 6);
  return {
    start_date: toDateOnlyLocal(start),
    end_date: toDateOnlyLocal(end),
  };
}

async function loadImageAsDataUrl(src: string): Promise<string | null> {
  try {
    const res = await fetch(src);
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : null);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function KpiCard({ title, value, description }: { title: string; value: string; description: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
        <CardDescription className="mt-2">{description}</CardDescription>
      </CardContent>
    </Card>
  );
}

type TooltipProps = {
  active?: boolean;
  label?: string;
  payload?: ReadonlyArray<{ name?: string; value?: number }>;
};

function CurrencyTooltip({ active, label, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border bg-popover p-3 text-xs text-popover-foreground shadow-md">
      {label ? <p className="mb-1 font-medium">{label}</p> : null}
      <div className="space-y-1">
        {payload.map((entry, idx) => (
          <p key={`${entry.name ?? "value"}-${idx}`}>
            <span className="text-muted-foreground">{entry.name}: </span>
            <span className="font-medium">{formatCurrency(Number(entry.value ?? 0))}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

export default function FinancialCommandCenterPage() {
  const range = defaultSixMonthRange();
  const [filters, setFilters] = useState<{
    start_date: string;
    end_date: string;
    granularity: FinancialHealthGranularity;
  }>({
    start_date: range.start_date,
    end_date: range.end_date,
    granularity: "month",
  });
  const { data, isLoading, isError, isFetching, error } = useFinancialHealth(filters);
  const financialData: FinancialHealthOut | null = data ?? null;
  const chartsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isError) {
      const message = error instanceof Error ? error.message : "Error de red al cargar salud financiera";
      toast.error(message);
    }
  }, [isError, error]);

  async function handleExportPdf() {
    if (!chartsRef.current) return;
    try {
      const canvas = await html2canvas(chartsRef.current, { scale: 2, backgroundColor: "#0a0a0a" });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = 210;
      const pageHeight = 297;
      const marginX = 10;
      const marginTop = 18;
      const marginBottom = 10;
      const contentWidth = pageWidth - marginX * 2;
      const fullImageHeight = (canvas.height * contentWidth) / canvas.width;
      const printableHeight = pageHeight - marginTop - marginBottom;
      const generatedAt = new Intl.DateTimeFormat("es-ES", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date());
      const filtersLine = `Rango: ${filters.start_date} a ${filters.end_date} · Granularidad: ${filters.granularity}`;

      const drawHeader = async () => {
        pdf.setFontSize(14);
        pdf.text("AB Logistics OS - Command Center Financiero", marginX, 12);
        pdf.setFontSize(9);
        pdf.text(filtersLine, marginX, 16);
        pdf.text(`Generado: ${generatedAt}`, pageWidth - 58, 16);
        const logoData = await loadImageAsDataUrl("/logo.svg");
        if (logoData) pdf.addImage(logoData, "PNG", 170, 6, 26, 10);
      };

      await drawHeader();

      let renderedHeight = 0;
      let pageIndex = 0;
      while (renderedHeight < fullImageHeight) {
        if (pageIndex > 0) {
          pdf.addPage();
          await drawHeader();
        }
        // Dibujamos la misma imagen desplazada en Y para "recortar" por página.
        const offsetY = marginTop - renderedHeight;
        pdf.addImage(imgData, "PNG", marginX, offsetY, contentWidth, fullImageHeight);
        renderedHeight += printableHeight;
        pageIndex += 1;
      }

      // Footer básico de paginación.
      const totalPages = pdf.getNumberOfPages();
      for (let i = 1; i <= totalPages; i += 1) {
        pdf.setPage(i);
        pdf.setFontSize(9);
        pdf.text(`Página ${i} de ${totalPages}`, pageWidth - 38, pageHeight - 4);
      }
      pdf.save(`ab-logistics-financial-${filters.start_date}_${filters.end_date}.pdf`);
    } catch {
      toast.error("No se pudo exportar el informe PDF.");
    }
  }

  function handleExportCsv() {
    if (!financialData?.series?.length) {
      toast.error("No hay datos para exportar CSV.");
      return;
    }
    exportToCSV(financialData.series, `financial-health-${filters.start_date}_${filters.end_date}.csv`);
  }

  const totalCo2Cost = useMemo(
    () => (financialData?.series ?? []).reduce((acc, row) => acc + row.co2_cost, 0),
    [financialData?.series],
  );

  const profitSeries = useMemo(
    () =>
      (financialData?.series ?? []).map((row) => {
        const marginEur = row.ingresos - row.gastos;
        const marginPct = row.ingresos > 0 ? (marginEur / row.ingresos) * 100 : 0;
        return { ...row, marginEur, marginPct };
      }),
    [financialData?.series],
  );

  const donutData = useMemo(() => {
    const gastosOperativos = (financialData?.series ?? []).reduce((acc, row) => acc + row.gastos, 0);
    return [
      { name: "Gasto Operativo Tradicional", value: Math.max(gastosOperativos, 0) },
      { name: "Coste Carbono (ETS)", value: Math.max(totalCo2Cost, 0) },
    ];
  }, [financialData?.series, totalCo2Cost]);

  const etsShare = useMemo(() => {
    const total = donutData.reduce((acc, row) => acc + row.value, 0);
    if (total <= 0) return 0;
    return (donutData[1].value / total) * 100;
  }, [donutData]);

  const liquiditySeries = useMemo(
    () =>
      (financialData?.series ?? []).map((row) => ({
        name: row.name,
        cash_flow_estimado: row.ingresos - row.gastos - row.co2_cost,
      })),
    [financialData?.series],
  );

  const themeColors = {
    primary: "hsl(var(--primary))",
    secondary: "hsl(var(--secondary))",
    accent: "hsl(var(--accent))",
    muted: "hsl(var(--muted-foreground))",
    positive: "hsl(var(--chart-2))",
    negative: "hsl(var(--destructive))",
  };

  return (
    <main className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Command Center Financiero</h1>
          <p className="text-sm text-muted-foreground">Fase 3 · BI financiero con foco en P&amp;L, rentabilidad y liquidez.</p>
          <Link href="/dashboard/bi" className="mt-2 inline-flex text-sm font-medium text-primary hover:underline">
            ← Inteligencia de negocio (rutas, márgenes, ESG)
          </Link>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExportPdf}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm hover:bg-muted/40"
          >
            <FileDown className="size-4" />
            Exportar PDF
          </button>
          <button
            type="button"
            onClick={handleExportCsv}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm hover:bg-muted/40"
          >
            <Download className="size-4" />
            Descargar CSV
          </button>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-3 rounded-xl border p-4 md:grid-cols-4">
        <DatePickerWithRange
          value={{ from: filters.start_date, to: filters.end_date }}
          onChange={(next) =>
            setFilters((prev) => ({
              ...prev,
              start_date: next.from,
              end_date: next.to,
            }))
          }
        />
        <label className="text-sm md:col-span-1">
          <span className="mb-1 block text-muted-foreground">Granularidad</span>
          <select
            value={filters.granularity}
            onChange={(e) =>
              setFilters((prev) => ({
                ...prev,
                granularity: e.target.value as FinancialHealthGranularity,
              }))
            }
            className="h-9 w-full rounded-md border bg-background px-2"
          >
            <option value="day">Día</option>
            <option value="week">Semana</option>
            <option value="month">Mes</option>
          </select>
        </label>
      </section>

      {isLoading ? <DashboardSkeleton /> : null}
      {!isLoading && isError ? (
        <Card>
          <CardContent className="py-8 text-sm text-destructive">No se pudieron cargar los datos financieros.</CardContent>
        </Card>
      ) : null}
      {!isLoading && !isError ? (
        <>
      <div
        ref={chartsRef}
        className={isFetching ? "opacity-70 transition-opacity" : "opacity-100 transition-opacity"}
      >
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="EBITDA"
          value={formatCurrency(financialData?.summary.ebitda ?? 0)}
          description="Ingresos operativos - costes operativos."
        />
        <KpiCard
          title="Margen Operativo"
          value={`${percentFormatter.format(financialData?.summary.operating_margin_pct ?? 0)}%`}
          description="Porcentaje de rentabilidad sobre ventas."
        />
        <KpiCard
          title="Cash Flow"
          value={formatCurrency(financialData?.summary.cash_flow ?? 0)}
          description="Saldo estimado de caja en el período."
        />
        <KpiCard
          title="Coste ETS"
          value={formatCurrency(totalCo2Cost)}
          description={`Precio ETS ref.: ${String(financialData?.meta?.ets_price_eur_per_ton ?? "—")} €/t CO2.`}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Evolución P&amp;L</CardTitle>
            <CardDescription>Ingresos y gastos con correlación de coste de carbono (eje derecho).</CardDescription>
          </CardHeader>
          <CardContent className="h-[340px]">
            {(financialData?.series?.length ?? 0) === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No hay datos en este periodo.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={financialData?.series ?? []}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`} />
                  <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => `${Math.round(Number(v))}`} />
                  <Tooltip content={<CurrencyTooltip />} />
                  <Legend />
                  <Bar dataKey="ingresos" name="Ingresos" fill={themeColors.primary} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="gastos" name="Gastos" fill={themeColors.secondary} radius={[4, 4, 0, 0]} />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="co2_cost"
                    name="Coste CO2"
                    stroke={themeColors.accent}
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tendencia de Rentabilidad</CardTitle>
            <CardDescription>
              Margen operativo (EUR, área) y margen % sobre ingresos del bucket (línea, eje derecho).
            </CardDescription>
          </CardHeader>
          <CardContent className="h-[340px]">
            {(financialData?.series?.length ?? 0) === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No hay datos en este periodo.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={profitSeries}>
                  <defs>
                    <linearGradient id="marginGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={themeColors.primary} stopOpacity={0.45} />
                      <stop offset="95%" stopColor={themeColors.primary} stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis yAxisId="left" tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`} />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    width={48}
                    tickFormatter={(v) => `${Number(v).toFixed(0)}%`}
                    domain={[0, "auto"]}
                  />
                  <Tooltip
                    content={({ active, label, payload }) => {
                      if (!active || !payload?.length) return null;
                      return (
                        <div className="rounded-md border bg-popover p-3 text-xs text-popover-foreground shadow-md">
                          {label ? <p className="mb-1 font-medium">{label}</p> : null}
                          <div className="space-y-1">
                            {payload.map((entry, idx) => {
                              const name = String(entry.name ?? "");
                              const v = Number(entry.value ?? 0);
                              const isPct = entry.dataKey === "marginPct";
                              return (
                                <p key={`${name}-${idx}`}>
                                  <span className="text-muted-foreground">{name}: </span>
                                  <span className="font-medium">
                                    {isPct ? `${v.toFixed(1)}%` : formatCurrency(v)}
                                  </span>
                                </p>
                              );
                            })}
                          </div>
                        </div>
                      );
                    }}
                  />
                  <Legend />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="marginEur"
                    name="Margen operativo (EUR)"
                    stroke={themeColors.primary}
                    fillOpacity={1}
                    fill="url(#marginGradient)"
                    strokeWidth={2}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="marginPct"
                    name="Margen %"
                    stroke="#a855f7"
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Estructura de Impacto</CardTitle>
            <CardDescription>Proporción del impuesto verde ETS sobre el gasto total.</CardDescription>
          </CardHeader>
          <CardContent className="h-[340px]">
            {(financialData?.series?.length ?? 0) === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No hay datos en este periodo.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip content={<CurrencyTooltip />} />
                  <Legend />
                  <Pie data={donutData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={72} outerRadius={110}>
                    <Cell fill={themeColors.secondary} />
                    <Cell fill={themeColors.accent} />
                  </Pie>
                  <text x="50%" y="49%" textAnchor="middle" dominantBaseline="middle" className="fill-foreground text-sm font-semibold">
                    ETS
                  </text>
                  <text x="50%" y="56%" textAnchor="middle" dominantBaseline="middle" className="fill-muted-foreground text-xs">
                    {percentFormatter.format(etsShare)}%
                  </text>
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Liquidez Mensual</CardTitle>
            <CardDescription>Cash flow estimado por mes (verde positivo, rojo negativo).</CardDescription>
          </CardHeader>
          <CardContent className="h-[340px]">
            {(financialData?.series?.length ?? 0) === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No hay datos en este periodo.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={liquiditySeries} layout="vertical" margin={{ left: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`} />
                  <YAxis type="category" dataKey="name" width={64} />
                  <Tooltip content={<CurrencyTooltip />} />
                  <Bar dataKey="cash_flow_estimado" name="Cash Flow estimado" radius={[0, 4, 4, 0]}>
                    {liquiditySeries.map((entry) => (
                      <Cell key={entry.name} fill={entry.cash_flow_estimado >= 0 ? themeColors.positive : themeColors.negative} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </section>
      </div>
      {isFetching ? (
        <div className="fixed bottom-4 right-4 inline-flex items-center gap-2 rounded-full border bg-background/90 px-3 py-1.5 text-xs shadow">
          <Loader2 className="size-3.5 animate-spin" />
          Actualizando datos...
        </div>
      ) : null}
        </>
      ) : null}
    </main>
  );
}

