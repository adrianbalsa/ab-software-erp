"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Package, MapPin, Euro, Bell, Route } from "lucide-react";
import Link from "next/link";
import { AlertasCriticas } from "@/components/AlertasCriticas";
import { AppShell } from "@/components/AppShell";
import { DashboardMotionFadeIn } from "@/components/dashboard/DashboardMotionFadeIn";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { LogisAdvisorChat } from "@/components/dashboard/LogisAdvisorChat";
import { CashFlowChart } from "@/components/dashboard/CashFlowChart";
import { CostBreakdownPie } from "@/components/dashboard/CostBreakdownPie";
import { EfficiencyKpiCard } from "@/components/dashboard/EfficiencyKpiCard";
import { AdvancedCharts } from "@/components/dashboard/AdvancedCharts";
import { BreakEvenAnalysis } from "@/components/dashboard/BreakEvenAnalysis";
import { EconomicAdvancedDashboard } from "@/components/dashboard/EconomicAdvancedDashboard";
import { EfficiencyMatrix } from "@/components/dashboard/EfficiencyMatrix";
import { SupportCard } from "@/components/docs/SupportCard";
import { EconomicOverview } from "@/components/EconomicOverview";
import { EmissionBadge } from "@/components/esg/EmissionBadge";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { AppErrorBoundary } from "@/components/ui/AppErrorBoundary";
import { toast } from "sonner";
import { useDashboardStats } from "@/hooks/useDashboardStats";
import { useEcoDashboard } from "@/hooks/useEcoDashboard";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";
import { useFleetAlerts } from "@/hooks/useFleetAlerts";
import { isAuthCredentialErrorMessage, isOwnerLike } from "@/lib/api";
import { useRole } from "@/hooks/useRole";

const OAUTH_WELCOME_KEY = "abl_oauth_welcome";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function Dashboard() {
  const router = useRouter();
  const { role } = useRole();
  useEffect(() => {
    if (role === "cliente") router.replace("/portal");
  }, [role, router]);
  const isOwner = isOwnerLike(role);
  const canFleetAlerts = isOwnerLike(role) || role === "traffic_manager";

  const { data, loading, error, refresh } = useFinanceDashboard({
    enabled: isOwner,
  });
  const {
    data: ecoData,
    loading: ecoLoading,
    error: ecoError,
    refresh: refreshEco,
  } = useEcoDashboard({ enabled: isOwner });
  const {
    data: statsOps,
    loading: statsLoading,
    error: statsError,
    refresh: refreshStats,
  } = useDashboardStats({ enabled: !isOwner });
  const {
    alerts: fleetAlerts,
    loading: fleetAlertsLoading,
    error: fleetAlertsError,
    refresh: refreshFleetAlerts,
  } = useFleetAlerts({ enabled: canFleetAlerts });
  const [welcomeToast, setWelcomeToast] = useState<ToastPayload | null>(null);

  const loadingAny = isOwner ? loading : statsLoading;

  useEffect(() => {
    try {
      if (sessionStorage.getItem(OAUTH_WELCOME_KEY) === "1") {
        sessionStorage.removeItem(OAUTH_WELCOME_KEY);
        queueMicrotask(() =>
          setWelcomeToast({
            id: Date.now(),
            message: "Bienvenido",
            tone: "success",
          }),
        );
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!isOwner || !error) return;
    if (isAuthCredentialErrorMessage(error)) {
      toast.error("Sesión no válida o expirada. Vuelve a iniciar sesión.", { id: "abl-dash-auth" });
    } else {
      toast.error(`KPI financieros: ${error}`, { id: "dash-finance-error" });
    }
  }, [isOwner, error]);

  useEffect(() => {
    if (isOwner || !statsError) return;
    if (isAuthCredentialErrorMessage(statsError)) {
      toast.error("Sesión no válida o expirada. Vuelve a iniciar sesión.", { id: "abl-dash-auth" });
    } else {
      toast.error(`KPI operativos: ${statsError}`, { id: "dash-stats-error" });
    }
  }, [isOwner, statsError]);

  useEffect(() => {
    if (!ecoError) return;
    if (isAuthCredentialErrorMessage(ecoError)) {
      toast.error("Sesión no válida o expirada. Vuelve a iniciar sesión.", { id: "abl-dash-auth" });
    } else {
      toast.error(`ESG: ${ecoError}`, { id: "dash-eco-error" });
    }
  }, [ecoError]);

  const onRefreshKpis = () => {
    if (isOwner) void refresh();
    if (isOwner) void refreshEco();
    else void refreshStats();
    if (canFleetAlerts) void refreshFleetAlerts();
  };

  return (
    <AppShell active="dashboard">
      <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
        <LogisAdvisorChat />
      </RoleGuard>
      <ToastHost toast={welcomeToast} onDismiss={() => setWelcomeToast(null)} durationMs={5200} />
      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
        <header className="z-10 flex h-16 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950/90 px-8 backdrop-blur-md">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">
              Cuadro de Mando Integral
            </h1>
            {!isOwner && (
              <p className="mt-0.5 text-xs text-zinc-500">
                Vista operativa · sin datos financieros globales
              </p>
            )}
          </div>
          <div className="flex items-center space-x-4">
            <button
              type="button"
              onClick={() => onRefreshKpis()}
              disabled={loadingAny}
              className="text-sm font-medium text-emerald-500 hover:text-emerald-400 disabled:opacity-50"
            >
              {loadingAny ? "Actualizando…" : "Actualizar KPIs"}
            </button>
            <span className="text-sm font-medium text-zinc-500">
              {new Date().toLocaleDateString("es-ES", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
            <button
              type="button"
              className="rounded-full bg-zinc-900/80 p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
              aria-label="Notificaciones"
            >
              <Bell className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="flex-1 space-y-6 p-8">
          {isOwner ? (
            <>
              <DashboardMotionFadeIn>
                <SupportCard />
              </DashboardMotionFadeIn>

              <DashboardMotionFadeIn delay={0.06} className="grid grid-cols-1 gap-6 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
                <div className="dashboard-bento p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="mb-1 text-sm font-medium text-zinc-400">EBITDA (real)</p>
                      <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
                        {loading ? "…" : data ? formatEUR(data.ebitda) : "—"}
                      </h3>
                    </div>
                    <div className="rounded-xl bg-emerald-500/15 p-3 text-emerald-400">
                      <TrendingUp className="h-6 w-6" />
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-zinc-500">
                    Ingresos − Gastos ·{" "}
                    <Link href="/finanzas" className="font-medium text-emerald-500 hover:text-emerald-400 hover:underline">
                      Ver dashboard financiero
                    </Link>
                  </p>
                </div>

                <div className="dashboard-bento p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="mb-1 text-sm font-medium text-zinc-400">Ingresos (operación)</p>
                      <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
                        {loading ? "…" : data ? formatEUR(data.ingresos) : "—"}
                      </h3>
                    </div>
                    <div className="rounded-xl bg-amber-500/15 p-3 text-amber-400">
                      <Euro className="h-6 w-6" />
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-zinc-500">
                    Bases facturadas (sin IVA) ·{" "}
                    <code className="text-xs text-zinc-400">GET /finance/dashboard</code>
                  </p>
                </div>

                <div className="dashboard-bento p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="mb-1 text-sm font-medium text-zinc-400">Gastos (operativos)</p>
                      <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
                        {loading ? "…" : data ? formatEUR(data.gastos) : "—"}
                      </h3>
                    </div>
                    <div className="rounded-xl bg-emerald-500/12 p-3 text-emerald-500">
                      <MapPin className="h-6 w-6" />
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-zinc-500">Suma de gastos en `gastos`</p>
                </div>

                <div className="dashboard-bento p-6">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="mb-1 text-sm font-medium text-zinc-400">Bultos</p>
                      <h3 className="text-3xl font-bold tracking-tight text-zinc-100">—</h3>
                    </div>
                    <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                      <Package className="h-6 w-6" />
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-zinc-500">
                    Margen neto/km y desglose en la sección inferior
                  </p>
                </div>
              </DashboardMotionFadeIn>

              <DashboardMotionFadeIn delay={0.1}>
              <section className="space-y-4" aria-labelledby="dash-advanced-heading">
                <h2
                  id="dash-advanced-heading"
                  className="text-lg font-semibold tracking-tight text-zinc-100"
                >
                  Tesorería, costes y eficiencia
                </h2>
                <p className="text-sm text-zinc-500">
                  Datos del Math Engine vía{" "}
                  <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-400">
                    GET /finance/dashboard
                  </code>
                </p>
                <EfficiencyKpiCard
                  loading={loading}
                  margenNetoKm={data?.margen_neto_km_mes_actual ?? null}
                  margenNetoKmMesAnterior={data?.margen_neto_km_mes_anterior ?? null}
                  variacionPct={data?.variacion_margen_km_pct ?? null}
                  kmFacturadosMes={data?.km_facturados_mes_actual ?? null}
                  kmFacturadosMesAnterior={data?.km_facturados_mes_anterior ?? null}
                />
                <AppErrorBoundary>
                  <EmissionBadge />
                </AppErrorBoundary>
                <div className="grid lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2">
                    <AppErrorBoundary>
                      <CashFlowChart
                        loading={loading}
                        data={data?.tesoreria_mensual ?? []}
                      />
                    </AppErrorBoundary>
                  </div>
                  <AppErrorBoundary>
                    <CostBreakdownPie
                      loading={loading}
                      data={data?.gastos_por_bucket_cinco ?? []}
                    />
                  </AppErrorBoundary>
                </div>
              </section>
              </DashboardMotionFadeIn>

              <DashboardMotionFadeIn delay={0.14}>
              <section className="space-y-4" aria-labelledby="dash-rentabilidad-avanzada">
                <h2
                  id="dash-rentabilidad-avanzada"
                  className="text-lg font-semibold tracking-tight text-zinc-100"
                >
                  Análisis de Rentabilidad Avanzada
                </h2>
                <p className="text-sm text-zinc-500">
                  Datos consolidados desde endpoints optimizados:
                  <code className="ml-1 rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-400">
                    GET /finance/dashboard
                  </code>
                  <code className="ml-1 rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-400">
                    GET /eco/dashboard/
                  </code>
                </p>
                <div className="grid gap-6 lg:grid-cols-2">
                  <AppErrorBoundary>
                    <EfficiencyMatrix
                      loading={loading || ecoLoading}
                      margenNetoKm={data?.margen_neto_km_mes_actual ?? null}
                      co2PerTonKm={ecoData?.co2_per_ton_km ?? null}
                      ingresosMensuales={data?.ingresos ?? 0}
                    />
                  </AppErrorBoundary>
                  <AppErrorBoundary>
                    <BreakEvenAnalysis
                      loading={loading}
                      monthly={data?.ingresos_vs_gastos_mensual ?? []}
                    />
                  </AppErrorBoundary>
                </div>
              </section>
              </DashboardMotionFadeIn>

              <DashboardMotionFadeIn delay={0.18}>
              <AppErrorBoundary>
                <EconomicOverview />
              </AppErrorBoundary>
              </DashboardMotionFadeIn>
              <DashboardMotionFadeIn delay={0.2}>
              <AppErrorBoundary>
                <EconomicAdvancedDashboard enabled={isOwner} />
              </AppErrorBoundary>
              </DashboardMotionFadeIn>
              <DashboardMotionFadeIn delay={0.22} className="w-full max-w-[100vw] overflow-x-auto">
                <AppErrorBoundary>
                  <AdvancedCharts />
                </AppErrorBoundary>
              </DashboardMotionFadeIn>
            </>
          ) : (
            <DashboardMotionFadeIn className="grid grid-cols-1 gap-6 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              <div className="dashboard-bento p-6 md:col-span-1">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="mb-1 text-sm font-medium text-zinc-400">Km (mes en curso)</p>
                    <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
                      {statsLoading
                        ? "…"
                        : statsOps != null
                          ? (statsOps.km_estimados ?? 0).toLocaleString("es-ES", {
                              maximumFractionDigits: 1,
                            })
                          : "—"}
                    </h3>
                  </div>
                  <div className="rounded-xl bg-emerald-500/12 p-3 text-emerald-500">
                    <Route className="h-6 w-6" />
                  </div>
                </div>
                <p className="mt-4 text-sm text-zinc-500">
                  Suma{" "}
                  <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-400">
                    km_estimados
                  </code>{" "}
                  de portes del mes ·{" "}
                  <code className="text-xs text-zinc-400">GET /dashboard/stats</code>
                </p>
              </div>

              <div className="dashboard-bento p-6 md:col-span-1">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="mb-1 text-sm font-medium text-zinc-400">Bultos (mes)</p>
                    <h3 className="text-3xl font-bold tracking-tight text-zinc-100">
                      {statsLoading ? "…" : statsOps != null ? (statsOps.bultos ?? 0) : "—"}
                    </h3>
                  </div>
                  <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                    <Package className="h-6 w-6" />
                  </div>
                </div>
                <p className="mt-4 text-sm text-zinc-500">Agregado operativo sin datos de facturación</p>
              </div>
            </DashboardMotionFadeIn>
          )}

          {canFleetAlerts && (
            <AlertasCriticas
              alerts={fleetAlerts}
              loading={fleetAlertsLoading}
              error={fleetAlertsError}
              onRetry={() => void refreshFleetAlerts()}
            />
          )}

          <div className="dashboard-bento overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/30 px-6 py-5 backdrop-blur-sm">
              <h2 className="text-lg font-semibold tracking-tight text-zinc-100">Accesos rápidos</h2>
              <div className="flex flex-wrap gap-4">
                <Link
                  href="/portes"
                  className="text-sm font-medium text-emerald-500 transition-colors hover:text-emerald-400"
                >
                  Portes
                </Link>
                <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
                  <Link href="/flota" className="text-sm font-medium text-emerald-500 hover:text-emerald-400 hover:underline">
                    Flota
                  </Link>
                </RoleGuard>
                {isOwner && (
                  <Link href="/finanzas" className="text-sm font-medium text-zinc-400 hover:text-zinc-200">
                    Finanzas
                  </Link>
                )}
              </div>
            </div>
            <div className="p-6 text-sm text-zinc-500">
              {isOwner ? (
                <>
                  Los KPI y gráficos avanzados usan{" "}
                  <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-zinc-400">
                    GET /finance/dashboard
                  </code>{" "}
                  con JWT (misma sesión que el resto de módulos).
                </>
              ) : (
                <>
                  Los indicadores de esta vista provienen de{" "}
                  <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-zinc-400">
                    GET /dashboard/stats
                  </code>{" "}
                  según tu rol; la facturación y el EBITDA solo están disponibles para el perfil{" "}
                  <strong className="font-medium text-zinc-300">owner</strong>.
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
