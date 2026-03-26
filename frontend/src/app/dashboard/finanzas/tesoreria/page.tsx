"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileDown, RefreshCw, Wallet } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { TreasuryRiskCharts } from "@/components/dashboard/TreasuryRiskCharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type FinanceEsgReport, type TreasuryRiskResponse } from "@/lib/api";

function formatEUR(value: number) {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function EmptyState() {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>Sin datos de tesoreria todavia</CardTitle>
        <CardDescription>
          Crea tu primer porte para empezar a ver la magia financiera en tiempo real.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-zinc-600">
          Cuando tengas actividad, aqui apareceran KPIs de riesgo y evolucion mensual de cobros.
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
      ? "border-blue-200"
      : tone === "green"
        ? "border-emerald-200"
        : tone === "amber"
          ? "border-amber-200"
          : "border-zinc-200";

  return (
    <Card className={`${toneClass} ${highlight ? "ring-2 ring-rose-300" : ""}`}>
      <CardHeader className="pb-1">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-zinc-600">{subtitle}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardTesoreriaPage() {
  const [data, setData] = useState<TreasuryRiskResponse | null>(null);
  const [esgReport, setEsgReport] = useState<FinanceEsgReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloadingCert, setDownloadingCert] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [risk, esg] = await Promise.all([
        api.finance.fetchTreasuryRisk(),
        api.finance.fetchEsgReport(),
      ]);
      setData(risk);
      setEsgReport(esg);
    } catch (e) {
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
          <main className="p-8">
            <p className="text-sm text-zinc-600">Acceso restringido: solo direccion.</p>
          </main>
        }
      >
        <main className="flex-1 min-h-0 overflow-y-auto p-8 space-y-6">
          <header className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-zinc-900 flex items-center gap-2">
                <Wallet className="w-6 h-6 text-blue-600" />
                Dashboard de Tesoreria y Riesgos
              </h1>
              <p className="text-sm text-zinc-500 mt-1">
                Seguimiento de deuda, cobertura SEPA y proyeccion de cash flow.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void loadData()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                Actualizar
              </button>
            </div>
          </header>

          {error && (
            <Card className="border-rose-200 bg-rose-50">
              <CardContent className="pt-6">
                <p className="text-sm text-rose-700">{error}</p>
              </CardContent>
            </Card>
          )}

          {loading && !data ? (
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-zinc-600">Cargando tesoreria...</p>
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
                <Card className="border-emerald-200 bg-emerald-50/40">
                  <CardHeader className="pb-1">
                    <CardTitle className="text-lg">Sostenibilidad ESG</CardTitle>
                    <CardDescription>
                      Resumen mensual para certificacion de huella de carbono.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-emerald-800">
                      Periodo {esgReport.periodo}:{" "}
                      <span className="font-semibold">
                        {esgReport.total_co2_kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg CO2
                      </span>{" "}
                      en {esgReport.total_portes} portes.
                    </p>
                    <button
                      type="button"
                      onClick={() => void downloadEsgCertificate()}
                      disabled={downloadingCert}
                      className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 px-3 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100/60 disabled:opacity-60"
                    >
                      <FileDown className="w-4 h-4" />
                      {downloadingCert ? "Descargando..." : "Descargar Certificado Mensual"}
                    </button>
                  </CardContent>
                </Card>
              )}

              {highRiskPct > 15 && (
                <Card className="border-amber-300 bg-amber-50">
                  <CardContent className="pt-6 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
                    <p className="text-sm text-amber-800">
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
            </>
          )}
        </main>
      </RoleGuard>
    </AppShell>
  );
}
