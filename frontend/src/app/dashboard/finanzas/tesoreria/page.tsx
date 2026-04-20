"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, FileDown, RefreshCw, Wallet } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { CreditAlertBanner } from "@/components/dashboard/CreditAlertBanner";
import { RiskRankingTable } from "@/components/dashboard/RiskRankingTable";
import { RouteMarginTable } from "@/components/dashboard/RouteMarginTable";
import { TreasuryRiskCharts } from "@/components/dashboard/TreasuryRiskCharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  api,
  type BankPendingReconciliationRow,
  type CreditAlert,
  type FinanceEsgReport,
  type RiskRankingRow,
  type RouteMarginRow,
  type TreasuryRiskResponse,
} from "@/lib/api";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import type { Catalog } from "@/i18n/catalog";
import { currencyLocale, formatCurrencyEUR } from "@/i18n/localeFormat";

const DEFAULT_GOCARDLESS_INSTITUTION =
  process.env.NEXT_PUBLIC_GOCARDLESS_INSTITUTION_ID ?? "SANDBOXFINANCE_SFIN0000";

function confidenceBadgeVariant(score: number): "default" | "warning" | "success" {
  if (score >= 0.85) return "success";
  if (score >= 0.5) return "default";
  return "warning";
}

function EmptyState({ t }: { t: Catalog["pages"]["tesoreria"] }) {
  return (
    <Card className="bunker-card border-dashed border-zinc-700">
      <CardHeader>
        <CardTitle className="text-zinc-100">{t.emptyTitle}</CardTitle>
        <CardDescription className="text-zinc-400">{t.emptyDesc}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-zinc-400">{t.emptyBody}</p>
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
  const { catalog, locale } = useOptionalLocaleCatalog();
  const p = catalog.pages;
  const numLoc = currencyLocale(locale);
  const fmtEur = (value: number) => formatCurrencyEUR(value, locale, { maximumFractionDigits: 0 });

  const [data, setData] = useState<TreasuryRiskResponse | null>(null);
  const [riskRanking, setRiskRanking] = useState<RiskRankingRow[] | null>(null);
  const [routeMarginRows, setRouteMarginRows] = useState<RouteMarginRow[]>([]);
  const [creditAlerts, setCreditAlerts] = useState<CreditAlert[]>([]);
  const [esgReport, setEsgReport] = useState<FinanceEsgReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingCert, setDownloadingCert] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bankPending, setBankPending] = useState<BankPendingReconciliationRow[]>([]);
  const [bankBusy, setBankBusy] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [risk, ranking, esg, alerts, margins, pendingBank] = await Promise.all([
        api.finance.fetchTreasuryRisk(),
        api.finance.getRiskRanking(),
        api.finance.fetchEsgReport(),
        api.finance.getCreditAlerts().catch(() => [] as CreditAlert[]),
        api.finance.getRouteMarginRanking().catch(() => [] as RouteMarginRow[]),
        api.banking.listPendingReconciliation().catch(() => [] as BankPendingReconciliationRow[]),
      ]);
      setData(risk);
      setRiskRanking(ranking);
      setEsgReport(esg);
      setCreditAlerts(alerts);
      setRouteMarginRows(margins);
      setBankPending(pendingBank);
    } catch (e) {
      setRiskRanking(null);
      setRouteMarginRows([]);
      setCreditAlerts([]);
      setBankPending([]);
      setError(e instanceof Error ? e.message : p.tesoreria.loadError);
    } finally {
      setLoading(false);
    }
  }, [p.tesoreria.loadError]);

  const connectBank = useCallback(async () => {
    setBankBusy(true);
    setError(null);
    try {
      const out = await api.banking.getConnectLink(DEFAULT_GOCARDLESS_INSTITUTION);
      if (out.link) window.location.assign(out.link);
    } catch (e) {
      setError(e instanceof Error ? e.message : p.tesoreria.connectError);
    } finally {
      setBankBusy(false);
    }
  }, [p.tesoreria.connectError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const downloadEsgCertificate = useCallback(async () => {
    setDownloadingCert(true);
    try {
      await api.finance.downloadEsgCertificatePdf();
    } catch (e) {
      setError(e instanceof Error ? e.message : p.tesoreria.certError);
    } finally {
      setDownloadingCert(false);
    }
  }, [p.tesoreria.certError]);

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
        allowedRoles={["owner", "admin"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-400">{p.tesoreria.roleFallback}</p>
          </main>
        }
      >
        <main className="min-h-0 flex-1 space-y-6 overflow-y-auto bg-zinc-950 p-8">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
                <Wallet className="h-6 w-6 text-emerald-500" aria-hidden />
                {p.tesoreria.title}
              </h1>
              <p className="mt-1 text-sm text-zinc-400">{p.tesoreria.subtitle}</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadData()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-60"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                {p.tesoreria.refresh}
              </button>
            </div>
          </header>

          <CreditAlertBanner alerts={creditAlerts} />

          <Card className="bunker-card border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg text-zinc-100">
                <Building2 className="h-5 w-5 text-sky-400" aria-hidden />
                {p.tesoreria.bankingTitle}
              </CardTitle>
              <CardDescription className="text-zinc-400">
                {p.tesoreria.bankingDesc}{" "}
                <code className="text-xs text-zinc-500">POST /api/v1/banking/reconcile</code>.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={bankBusy}
                  onClick={() => void connectBank()}
                  className="border-sky-500/40 bg-sky-950/40 text-sky-100 hover:bg-sky-950/70"
                >
                  {bankBusy ? p.tesoreria.redirecting : p.tesoreria.connectBank}
                </Button>
                <span className="text-xs text-zinc-500">
                  {p.tesoreria.sandboxInst} {DEFAULT_GOCARDLESS_INSTITUTION}
                </span>
              </div>
              {bankPending.length === 0 ? (
                <p className="text-sm text-zinc-500">{p.tesoreria.noPending}</p>
              ) : (
                <div className="overflow-x-auto rounded-md border border-zinc-800">
                  <table className="w-full min-w-[520px] text-left text-sm text-zinc-200">
                    <thead className="border-b border-zinc-800 bg-zinc-900/50 text-xs uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-3 py-2">{p.tesoreria.thDate}</th>
                        <th className="px-3 py-2">{p.tesoreria.thConcept}</th>
                        <th className="px-3 py-2 text-right">{p.tesoreria.thAmount}</th>
                        <th className="px-3 py-2">{p.tesoreria.thConfidence}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bankPending.map((row) => (
                        <tr key={row.transaction_id} className="border-b border-zinc-800/80 last:border-0">
                          <td className="px-3 py-2 whitespace-nowrap text-zinc-300">{row.booking_date}</td>
                          <td className="max-w-[280px] truncate px-3 py-2 text-zinc-400" title={row.description ?? ""}>
                            {row.description || "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-medium tabular-nums">
                            {fmtEur(row.amount)}
                          </td>
                          <td className="px-3 py-2">
                            <Badge variant={confidenceBadgeVariant(row.ia_confidence)}>
                              {(row.ia_confidence * 100).toFixed(0)}%
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

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
                <p className="text-sm text-zinc-400">{p.tesoreria.loading}</p>
              </CardContent>
            </Card>
          ) : !data || !hasAnyData ? (
            <EmptyState t={p.tesoreria} />
          ) : (
            <>
              <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <KpiCard
                  title={p.tesoreria.kpiPending}
                  value={fmtEur(total)}
                  subtitle={p.tesoreria.kpiPendingSub}
                  tone="blue"
                />
                <KpiCard
                  title={p.tesoreria.kpiSepa}
                  value={`${sepaCoveragePct.toLocaleString(numLoc, { maximumFractionDigits: 1 })}%`}
                  subtitle={`${fmtEur(sepa)} ${p.tesoreria.kpiSepaSubG} ${fmtEur(total)}`}
                  tone="green"
                />
                <KpiCard
                  title={p.tesoreria.kpiRisk}
                  value={fmtEur(highRisk)}
                  subtitle={`${p.tesoreria.kpiRiskSub} ${highRiskPct.toLocaleString(numLoc, { maximumFractionDigits: 1 })}% ${p.tesoreria.kpiRiskSub2}`}
                  tone="amber"
                  highlight={highRiskPct > 15}
                />
              </section>

              {esgReport && (
                <Card className="bunker-card border-emerald-500/35">
                  <CardHeader className="pb-1">
                    <CardTitle className="text-lg text-zinc-100">{p.tesoreria.esgTitle}</CardTitle>
                    <CardDescription className="text-zinc-400">{p.tesoreria.esgDesc}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-zinc-300">
                      {p.tesoreria.esgPeriod} {esgReport.periodo}:{" "}
                      <span className="font-semibold text-emerald-400">
                        {esgReport.total_co2_kg.toLocaleString(numLoc, { maximumFractionDigits: 2 })}{" "}
                        {p.tesoreria.esgCo2Unit}
                      </span>{" "}
                      {p.tesoreria.esgIn} {esgReport.total_portes} {p.tesoreria.esgPortes}
                    </p>
                    <button
                      type="button"
                      onClick={() => void downloadEsgCertificate()}
                      disabled={downloadingCert}
                      className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-950/30 px-3 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-950/50 disabled:opacity-60"
                    >
                      <FileDown className="w-4 h-4" />
                      {downloadingCert ? p.tesoreria.certDownloading : p.tesoreria.certDownload}
                    </button>
                  </CardContent>
                </Card>
              )}

              {highRiskPct > 15 && (
                <Card className="border border-amber-500/40 bg-amber-950/30">
                  <CardContent className="flex items-start gap-3 pt-6">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" aria-hidden />
                    <p className="text-sm text-amber-200">{p.tesoreria.riskBanner}</p>
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
                  <CardTitle className="text-lg text-zinc-100">{p.tesoreria.rankRiskTitle}</CardTitle>
                  <CardDescription className="text-zinc-400">{p.tesoreria.rankRiskDesc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <RiskRankingTable rows={riskRanking ?? []} />
                </CardContent>
              </Card>

              <Card className="bunker-card">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg text-zinc-100">{p.tesoreria.rankMarginTitle}</CardTitle>
                  <CardDescription className="text-zinc-400">{p.tesoreria.rankMarginDesc}</CardDescription>
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
