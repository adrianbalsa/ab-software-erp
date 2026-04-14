"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileDown, RefreshCw, Wallet } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { CreditAlertBanner } from "@/components/dashboard/CreditAlertBanner";
import { RiskRankingTable } from "@/components/dashboard/RiskRankingTable";
import { RouteMarginTable } from "@/components/dashboard/RouteMarginTable";
import { TreasuryRiskCharts } from "@/components/dashboard/TreasuryRiskCharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  api,
  type CreditAlert,
  type FinanceEsgReport,
  type RiskRankingRow,
  type RouteMarginRow,
  type TreasuryRiskResponse,
} from "@/lib/api";

function formatEUR(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function EmptyState() {
  return (
    <Card className="bunker-card border-dashed border-zinc-700">
      <CardHeader>
        <CardTitle className="text-zinc-100">Sin datos de tesorería todavía</CardTitle>
        <CardDescription className="text-zinc-400">
          Crea tu primer porte para empezar a ver la magia financiera en tiempo real.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-zinc-400">
          Cuando tengas actividad, aquí aparecerán KPIs de riesgo y evolución mensual de cobros.
        </p>
      </CardContent>
    </Card>
  );
}

function KpiCard({
  title,
  value,
  subtitle,
  tone = "default",
  highlight = false,
}: {
  title: string;
  value: string;
  subtitle: string;
  tone?: "default" | "blue" | "green" | "amber";
  highlight?: boolean;
}) {
  const toneClass =
    tone === "blue"
      ? "border-emerald-500/35"
      : tone === "green"
        ? "border-emerald-500/50"
        : tone === "amber"
          ? "border-amber-500/40"
          : "border-zinc-800";

  return (
    <Card
      className={`bunker-card ${toneClass} ${highlight ? "ring-2 ring-rose-500/40" : ""}`}
    >
      <CardHeader className="pb-1">
        <CardDescription className="text-zinc-400">{title}</CardDescription>
        <CardTitle className="text-2xl text-zinc-100">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-zinc-500">{subtitle}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardTesoreriaPage() {
  const [data, setData] = useState<TreasuryRiskResponse | null>(null);
  const [riskRanking, setRiskRanking] = useState<RiskRankingRow[] | null>(null);
  const [routeMarginRows, setRouteMarginRows] = useState<RouteMarginRow[]>([]);
  const [creditAlerts, setCreditAlerts] = useState<CreditAlert[]>([]);
  const [esgReport, setEsgReport] = useState<FinanceEsgReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingCert, setDownloadingCert] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [risk, ranking, esg, alerts, margins] = await Promise.all([
        api.finance.fetchTreasuryRisk(),
        api.finance.getRiskRanking(),
        api.finance.fetchEsgReport(),
        api.finance.getCreditAlerts().catch(() => [] as CreditAlert[]),
        api.finance.getRouteMarginRanking().catch(() => [] as RouteMarginRow[]),
      ]);
      setData(risk);
      setRiskRanking(ranking);
      setEsgReport(esg);
      setCreditAlerts(alerts);
      setRouteMarginRows(margins);
    } catch (e) {
      setRiskRanking(null);
      setRouteMarginRows([]);
      setCreditAlerts([]);
      setError(e instanceof Error ? e.message : "No se pudo cargar la tesoreria");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const downloadEsgCertificate = useCallback(async () => {
    setDownloadingCert(true);
    try {
      await api.finance.downloadEsgCertificatePdf();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo descargar el certificado");
    } finally {
      setDownloadingCert(false);
    }
  }, []);

  const total = data?.total_pendiente ?? 0;
  const sepa = data?.garantizado_sepa ?? 0;
  const highRisk = data?.en_riesgo_alto ?? 0;

  const sepaCoveragePct = useMemo(() => {
    if (total <= 0) return 0;
    return (sepa / total) * 100;
  }, [sepa, total]);

  const highRiskPct = useMemo(() => {
    if (total <= 0) return 0;
    return (highRisk / total) * 100;
  }, [highRisk, total]);

  const hasAnyData =
    total > 0 || (data?.cashflow_trend ?? []).some((p) => p.cobrado > 0 || p.pendiente > 0);

  return (
    <AppShell active="tesoreria">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-400">Acceso restringido: solo dirección.</p>
          </main>
        }
      >
        <main className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-zinc-950 p-8">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
                <Wallet className="h-6 w-6 text-emerald-500" aria-hidden />
                Dashboard de Tesorería y Riesgos
              </h1>
              <p className="mt-1 text-sm text-zinc-400">
                Seguimiento de deuda, cobertura SEPA y proyección de cash flow.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadData()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-60"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                Actualizar
              </button>
            </div>
          </header>

          <CreditAlertBanner alerts={creditAlerts} />

          {error && (
            <Card className="border border-rose-500/35 bg-rose-950/40">
              <CardContent className="pt-6">
                <p className="text-sm text-rose-300">{error}</p>
              </CardContent>
            </Card>
          )}

          {loading && !data ? (
            <Card className="bunker-card">
              <CardContent className="pt-6">
                <p className="text-sm text-zinc-400">Cargando tesorería…</p>
              </CardContent>
            </Card>
          ) : !data || !hasAnyData ? (
            <EmptyState />
          ) : (
            <>
              <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <KpiCard
                  title="Caja Pendiente"
                  value={formatEUR(total)}
                  subtitle="Total pendiente de cobro actual"
                  tone="blue"
                />
                <KpiCard
                  title="Cobertura SEPA"
                  value={`${sepaCoveragePct.toLocaleString("es-ES", { maximumFractionDigits: 1 })}%`}
                  subtitle={`${formatEUR(sepa)} garantizado sobre ${formatEUR(total)}`}
                  tone="green"
                />
                <KpiCard
                  title="Alerta de Riesgo"
                  value={formatEUR(highRisk)}
                  subtitle={`Exposicion alta: ${highRiskPct.toLocaleString("es-ES", { maximumFractionDigits: 1 })}% del total`}
                  tone="amber"
                  highlight={highRiskPct > 15}
                />
              </section>

              {esgReport && (
                <Card className="bunker-card border-emerald-500/35">
                  <CardHeader className="pb-1">
                    <CardTitle className="text-lg text-zinc-100">Sostenibilidad ESG</CardTitle>
                    <CardDescription className="text-zinc-400">
                      Resumen mensual para certificación de huella de carbono.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-zinc-300">
                      Periodo {esgReport.periodo}:{" "}
                      <span className="font-semibold text-emerald-400">
                        {esgReport.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg CO2
                      </span>{" "}
                      en {esgReport.total_portes} portes.
                    </p>
                    <button
                      type="button"
                      onClick={() => void downloadEsgCertificate()}
                      disabled={downloadingCert}
                      className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-950/50 disabled:opacity-60"
                    >
                      <FileDown className="w-4 h-4" />
                      {downloadingCert ? "Descargando..." : "Descargar Certificado Mensual"}
                    </button>
                  </CardContent>
                </Card>
              )}

              {highRiskPct > 15 && (
                <Card className="border border-amber-500/40 bg-amber-950/30">
                  <CardContent className="flex items-start gap-3 pt-6">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" aria-hidden />
                    <p className="text-sm text-amber-200">
                      Riesgo alto por encima del 15%. Conviene priorizar seguimiento de cobro y
                      revision de limites.
                    </p>
                  </CardContent>
                </Card>
              )}

              <TreasuryRiskCharts
                totalPending={total}
                sepaGuaranteed={sepa}
                highRisk={highRisk}
                trendData={data.cashflow_trend}
              />

              <Card className="bunker-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg text-zinc-100">Ranking de riesgo por cliente</CardTitle>
                  <CardDescription className="text-zinc-400">
                    Top exposiciones por valor en riesgo (
                    <span className="font-serif italic">V</span>
                    <sub className="text-[10px]">r</sub>
                    ). Barras relativas al máximo del listado.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RiskRankingTable rows={riskRanking ?? []} />
                </CardContent>
              </Card>

              <Card className="bunker-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg text-zinc-100">Ranking de margen por ruta</CardTitle>
                  <CardDescription className="text-zinc-400">
                    Top rutas por margen neto (
                    <span className="font-serif italic">M</span>
                    <sub className="text-[10px]">n</sub>
                    ); coste operativo estimado por km de la empresa.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RouteMarginTable rows={routeMarginRows} />
                </CardContent>
              </Card>
            </>
          )}
        </main>
      </RoleGuard>
    </AppShell>
  );
}
