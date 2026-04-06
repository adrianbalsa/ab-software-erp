"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Package, MapPin, Euro, Bell, Route } from "lucide-react";
import Link from "next/link";
import { AlertasCriticas } from "@/components/AlertasCriticas";
import { AppShell } from "@/components/AppShell";
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
import { useDashboardStats } from "@/hooks/useDashboardStats";
import { useEcoDashboard } from "@/hooks/useEcoDashboard";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";
import { useFleetAlerts } from "@/hooks/useFleetAlerts";
import { isOwnerLike } from "@/lib/api";
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
  const [toast, setToast] = useState<ToastPayload | null>(null);

  const loadingAny = isOwner ? loading : statsLoading;

  useEffect(() => {
    try {
      if (sessionStorage.getItem(OAUTH_WELCOME_KEY) === "1") {
        sessionStorage.removeItem(OAUTH_WELCOME_KEY);
        queueMicrotask(() =>
          setToast({
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
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={5200} />
      <main className="flex-1 flex flex-col overflow-y-auto min-h-0">
        <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 z-10">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
              Cuadro de Mando Integral
            </h1>
            {!isOwner && (
              <p className="text-xs text-slate-500 mt-0.5">
                Vista operativa · sin datos financieros globales
              </p>
            )}
          </div>
          <div className="flex items-center space-x-4">
            <button
              type="button"
              onClick={() => onRefreshKpis()}
              disabled={loadingAny}
              className="text-sm font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
            >
              {loadingAny ? "Actualizando…" : "Actualizar KPIs"}
            </button>
            <span className="text-sm text-slate-500 font-medium">
              {new Date().toLocaleDateString("es-ES", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
            <button className="p-2 text-slate-400 hover:text-slate-600 bg-slate-100 rounded-full transition-colors">
              <Bell className="w-5 h-5" />
            </button>
          </div>
        </header>

        <div className="p-8 space-y-6 flex-1">
          {isOwner && error && (
            <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-lg text-sm">
              KPI financieros: {error} (¿iniciaste sesión?).
            </div>
          )}
          {!isOwner && statsError && (
            <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-lg text-sm">
              KPI operativos: {statsError} (¿iniciaste sesión?).
            </div>
          )}

          {isOwner ? (
            <>
              <SupportCard />

              <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="ab-card p-6 rounded-2xl">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-slate-500 mb-1">
                        EBITDA (real)
                      </p>
                      <h3 className="text-3xl font-bold text-slate-800">
                        {loading ? "…" : data ? formatEUR(data.ebitda) : "—"}
                      </h3>
                    </div>
                    <div className="p-3 bg-emerald-50 rounded-xl text-emerald-600">
                      <TrendingUp className="w-6 h-6" />
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mt-4">
                    Ingresos − Gastos ·{" "}
                    <Link href="/finanzas" className="text-[#2563eb] font-medium hover:underline">
                      Ver dashboard financiero
                    </Link>
                  </p>
                </div>

                <div className="ab-card p-6 rounded-2xl">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-slate-500 mb-1">
                        Ingresos (operación)
                      </p>
                      <h3 className="text-3xl font-bold text-slate-800">
                        {loading ? "…" : data ? formatEUR(data.ingresos) : "—"}
                      </h3>
                    </div>
                    <div className="p-3 bg-amber-50 rounded-xl text-amber-600">
                      <Euro className="w-6 h-6" />
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mt-4">
                    Bases facturadas (sin IVA) ·{" "}
                    <code className="text-xs">GET /finance/dashboard</code>
                  </p>
                </div>

                <div className="ab-card p-6 rounded-2xl">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-slate-500 mb-1">
                        Gastos (operativos)
                      </p>
                      <h3 className="text-3xl font-bold text-slate-800">
                        {loading ? "…" : data ? formatEUR(data.gastos) : "—"}
                      </h3>
                    </div>
                    <div className="p-3 bg-blue-50 rounded-xl text-blue-600">
                      <MapPin className="w-6 h-6" />
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mt-4">
                    Suma de gastos en `gastos`
                  </p>
                </div>

                <div className="ab-card p-6 rounded-2xl">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-slate-500 mb-1">
                        Bultos
                      </p>
                      <h3 className="text-3xl font-bold text-slate-800">—</h3>
                    </div>
                    <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
                      <Package className="w-6 h-6" />
                    </div>
                  </div>
                  <p className="text-sm text-slate-500 mt-4">
                    Margen neto/km y desglose en la sección inferior
                  </p>
                </div>
              </div>

              <section className="space-y-4" aria-labelledby="dash-advanced-heading">
                <h2
                  id="dash-advanced-heading"
                  className="text-lg font-bold text-[#0b1224] tracking-tight"
                >
                  Tesorería, costes y eficiencia
                </h2>
                <p className="text-sm text-slate-500">
                  Datos del Math Engine vía{" "}
                  <code className="bg-slate-100 px-1 rounded text-xs">GET /finance/dashboard</code>
                </p>
                <EfficiencyKpiCard
                  loading={loading}
                  margenNetoKm={data?.margen_neto_km_mes_actual ?? null}
                  margenNetoKmMesAnterior={data?.margen_neto_km_mes_anterior ?? null}
                  variacionPct={data?.variacion_margen_km_pct ?? null}
                  kmFacturadosMes={data?.km_facturados_mes_actual ?? null}
                  kmFacturadosMesAnterior={data?.km_facturados_mes_anterior ?? null}
                />
                <EmissionBadge />
                <div className="grid lg:grid-cols-3 gap-6">
                  <div className="lg:col-span-2">
                    <CashFlowChart
                      loading={loading}
                      data={data?.tesoreria_mensual ?? []}
                    />
                  </div>
                  <CostBreakdownPie
                    loading={loading}
                    data={data?.gastos_por_bucket_cinco ?? []}
                  />
                </div>
              </section>

              <section className="space-y-4" aria-labelledby="dash-rentabilidad-avanzada">
                <h2
                  id="dash-rentabilidad-avanzada"
                  className="text-lg font-bold text-[#0b1224] tracking-tight"
                >
                  Análisis de Rentabilidad Avanzada
                </h2>
                <p className="text-sm text-slate-500">
                  Datos consolidados desde endpoints optimizados:
                  <code className="bg-slate-100 px-1 rounded text-xs ml-1">
                    GET /finance/dashboard
                  </code>
                  <code className="bg-slate-100 px-1 rounded text-xs ml-1">
                    GET /eco/dashboard/
                  </code>
                </p>
                {ecoError ? (
                  <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-lg text-sm">
                    ESG: {ecoError}
                  </div>
                ) : null}
                <div className="grid lg:grid-cols-2 gap-6">
                  <EfficiencyMatrix
                    loading={loading || ecoLoading}
                    margenNetoKm={data?.margen_neto_km_mes_actual ?? null}
                    co2PerTonKm={ecoData?.co2_per_ton_km ?? null}
                    ingresosMensuales={data?.ingresos ?? 0}
                  />
                  <BreakEvenAnalysis
                    loading={loading}
                    monthly={data?.ingresos_vs_gastos_mensual ?? []}
                  />
                </div>
              </section>

              <EconomicOverview />
              <EconomicAdvancedDashboard enabled={isOwner} />
              <div className="w-full max-w-[100vw] overflow-x-auto">
                <AdvancedCharts />
              </div>
            </>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="ab-card p-6 rounded-2xl md:col-span-1">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium text-slate-500 mb-1">
                      Km (mes en curso)
                    </p>
                    <h3 className="text-3xl font-bold text-slate-800">
                      {statsLoading
                        ? "…"
                        : statsOps != null
                          ? (statsOps.km_estimados ?? 0).toLocaleString("es-ES", {
                              maximumFractionDigits: 1,
                            })
                          : "—"}
                    </h3>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-xl text-blue-600">
                    <Route className="w-6 h-6" />
                  </div>
                </div>
                <p className="text-sm text-slate-500 mt-4">
                  Suma <code className="text-xs bg-slate-100 px-1 rounded">km_estimados</code> de
                  portes del mes · <code className="text-xs">GET /dashboard/stats</code>
                </p>
              </div>

              <div className="ab-card p-6 rounded-2xl md:col-span-1">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium text-slate-500 mb-1">
                      Bultos (mes)
                    </p>
                    <h3 className="text-3xl font-bold text-slate-800">
                      {statsLoading ? "…" : statsOps != null ? (statsOps.bultos ?? 0) : "—"}
                    </h3>
                  </div>
                  <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600">
                    <Package className="w-6 h-6" />
                  </div>
                </div>
                <p className="text-sm text-slate-500 mt-4">
                  Agregado operativo sin datos de facturación
                </p>
              </div>
            </div>
          )}

          {canFleetAlerts && (
            <AlertasCriticas
              alerts={fleetAlerts}
              loading={fleetAlertsLoading}
              error={fleetAlertsError}
              onRetry={() => void refreshFleetAlerts()}
            />
          )}

          <div className="ab-card rounded-2xl overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100/80 flex justify-between items-center bg-slate-50/50">
              <h2 className="text-lg font-bold text-slate-800">Accesos rápidos</h2>
              <div className="flex gap-4 flex-wrap">
                <Link
                  href="/portes"
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Portes
                </Link>
                <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
                  <Link
                    href="/flota"
                    className="text-sm font-medium text-[#2563eb] hover:underline"
                  >
                    Flota
                  </Link>
                </RoleGuard>
                {isOwner && (
                  <Link
                    href="/finanzas"
                    className="text-sm font-medium text-slate-600 hover:text-slate-800"
                  >
                    Finanzas
                  </Link>
                )}
              </div>
            </div>
            <div className="p-6 text-sm text-slate-600">
              {isOwner ? (
                <>
                  Los KPI y gráficos avanzados usan{" "}
                  <code className="bg-slate-100 px-1 rounded">GET /finance/dashboard</code> con JWT
                  (misma sesión que el resto de módulos).
                </>
              ) : (
                <>
                  Los indicadores de esta vista provienen de{" "}
                  <code className="bg-slate-100 px-1 rounded">GET /dashboard/stats</code> según tu
                  rol; la facturación y el EBITDA solo están disponibles para el perfil{" "}
                  <strong className="font-medium">owner</strong>.
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
