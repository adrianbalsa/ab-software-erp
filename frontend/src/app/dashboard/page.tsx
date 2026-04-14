"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, Package, MapPin, Euro, Bell, Route, Lock, Sparkles, UploadCloud, Truck } from "lucide-react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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
import { API_BASE, apiFetch, isAuthCredentialErrorMessage, isOwnerLike, jwtPayload } from "@/lib/api";
import { useRole } from "@/hooks/useRole";

const OAUTH_WELCOME_KEY = "abl_oauth_welcome";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

const PLACEHOLDER_CHART_DATA = [
  { label: "Ene", value: 12 },
  { label: "Feb", value: 16 },
  { label: "Mar", value: 14 },
  { label: "Abr", value: 20 },
  { label: "May", value: 18 },
  { label: "Jun", value: 24 },
];

function PlaceholderWelcomeChart({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="dashboard-bento relative h-[280px] overflow-hidden p-6">
      <div className="mb-4">
        <p className="text-sm font-medium text-zinc-400">{title}</p>
        <p className="text-xs text-zinc-500">{hint}</p>
      </div>
      <div className="h-[170px] opacity-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={PLACEHOLDER_CHART_DATA}>
            <defs>
              <linearGradient id="welcome-placeholder-gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#34d399" stopOpacity={0.5} />
                <stop offset="95%" stopColor="#34d399" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
            <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ stroke: "#52525b" }}
              contentStyle={{ backgroundColor: "#18181b", borderColor: "#3f3f46", borderRadius: 12 }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#34d399"
              strokeWidth={2}
              fill="url(#welcome-placeholder-gradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-zinc-950/55 backdrop-blur-[1px]">
        <div className="rounded-xl border border-emerald-500/30 bg-zinc-900/90 px-4 py-3 text-center shadow-lg shadow-emerald-500/10">
          <p className="text-sm font-semibold text-zinc-100">Get Started</p>
          <p className="text-xs text-zinc-400">Sube tu primera factura para desbloquear esta vista</p>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const { role } = useRole();
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [onboarded, setOnboarded] = useState(true);

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
  const radarLocked = isOwner
    ? !data || (data.ingresos ?? 0) <= 0
    : !statsOps || ((statsOps.km_estimados ?? 0) <= 0 && (statsOps.bultos ?? 0) <= 0);

  const companyType = useMemo(() => {
    const payload = jwtPayload() as Record<string, unknown> | null;
    if (!payload) return "empresa logística";
    const userMeta = payload.user_metadata as Record<string, unknown> | undefined;
    const appMeta = payload.app_metadata as Record<string, unknown> | undefined;
    const raw =
      userMeta?.company_type ??
      userMeta?.tipo_empresa ??
      appMeta?.company_type ??
      appMeta?.tipo_empresa ??
      payload.company_type ??
      payload.tipo_empresa;
    return typeof raw === "string" && raw.trim().length > 0 ? raw.trim() : "empresa logística";
  }, []);

  const aiGreeting = useMemo(() => {
    const lower = companyType.toLowerCase();
    if (lower.includes("frio") || lower.includes("frigor")) {
      return "Empieza configurando tu flota para activar recomendaciones de rutas con control de frío.";
    }
    if (lower.includes("ultima milla") || lower.includes("paqueter")) {
      return "Te recomiendo subir primero una factura para calcular margen por entrega desde el día uno.";
    }
    if (lower.includes("internacional")) {
      return "Configura la flota primero para estimar CO2 y costes por corredor internacional.";
    }
    return "Primer paso recomendado: sube tu primera factura para que AB Logistics AI active tu radar operativo.";
  }, [companyType]);

  const isWelcomeOwnerDashboard = useMemo(() => {
    if (!isOwner || loading || ecoLoading || !onboarded) return false;
    const hasFinanceData =
      !!data &&
      ((data.ingresos ?? 0) > 0 ||
        (data.gastos ?? 0) > 0 ||
        Math.abs(data.ebitda ?? 0) > 0 ||
        (data.ingresos_vs_gastos_mensual?.some((row) => (row.ingresos ?? 0) > 0 || (row.gastos ?? 0) > 0) ?? false));
    const hasEcoData =
      !!ecoData &&
      ((ecoData.co2_kg_portes_facturados ?? 0) > 0 ||
        (ecoData.num_portes_facturados ?? 0) > 0 ||
        (ecoData.co2_per_ton_km ?? 0) > 0);
    return !hasFinanceData && !hasEcoData;
  }, [isOwner, loading, ecoLoading, onboarded, data, ecoData]);

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
    let isMounted = true;
    const verifyOnboardingState = async () => {
      try {
        const res = await apiFetch(`${API_BASE}/empresa/quota`, { credentials: "include" });
        if (!isMounted) return;
        if (res.ok) {
          setOnboarded(true);
          return;
        }
        if (res.status === 401 || res.status === 403) {
          setOnboarded(false);
          router.replace("/onboarding");
          return;
        }
      } catch {
        // Let the dashboard continue when network is flaky.
      } finally {
        if (isMounted) setOnboardingChecked(true);
      }
    };
    void verifyOnboardingState();
    return () => {
      isMounted = false;
    };
  }, [router]);

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

  if (!onboardingChecked) {
    return (
      <AppShell active="dashboard">
        <main className="flex min-h-0 flex-1 items-center justify-center bg-zinc-950">
          <p className="text-sm text-zinc-400">Preparando tu dashboard...</p>
        </main>
      </AppShell>
    );
  }

  if (!onboarded) return null;

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
              {isWelcomeOwnerDashboard ? (
                <>
                  <DashboardMotionFadeIn>
                    <div className="dashboard-bento grid gap-4 p-6 lg:grid-cols-[1.4fr_1fr]">
                      <div className="space-y-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-400">AB Logistics AI</p>
                        <h2 className="text-xl font-semibold text-zinc-100">Bienvenido, todo listo para empezar</h2>
                        <p className="text-sm text-zinc-400">
                          Hemos detectado tu perfil como <span className="font-medium text-zinc-200">{companyType}</span>.
                        </p>
                        <p className="text-sm text-zinc-300">{aiGreeting}</p>
                      </div>
                      <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
                        <div className="mb-2 flex items-center gap-2 text-zinc-200">
                          <Sparkles className="h-4 w-4 text-emerald-400" />
                          <p className="text-sm font-medium">Siguiente mejor acción</p>
                        </div>
                        <p className="text-sm text-zinc-400">
                          Sube una primera factura para ver EBITDA, coste por km y alertas inteligentes.
                        </p>
                        <Link
                          href="/facturas/nueva"
                          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-emerald-400"
                        >
                          <UploadCloud className="h-4 w-4" />
                          Empezar ahora
                        </Link>
                      </div>
                    </div>
                  </DashboardMotionFadeIn>

                  <DashboardMotionFadeIn delay={0.05} className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <PlaceholderWelcomeChart
                      title="EBITDA estimado"
                      hint="Vista de ejemplo hasta que cargues tu primera operación real."
                    />
                    <PlaceholderWelcomeChart
                      title="CO2 por tonelada-km"
                      hint="Activa tu panel ESG en cuanto registres tus primeros portes."
                    />
                  </DashboardMotionFadeIn>

                  <DashboardMotionFadeIn delay={0.1} className="grid grid-cols-1 gap-6 md:grid-cols-3">
                    <Link href="/facturas/nueva" className="dashboard-bento group p-5 transition hover:border-emerald-500/50">
                      <div className="mb-3 inline-flex rounded-lg bg-emerald-500/15 p-2 text-emerald-400">
                        <UploadCloud className="h-5 w-5" />
                      </div>
                      <h3 className="text-base font-semibold text-zinc-100">Subir mi primera factura</h3>
                      <p className="mt-1 text-sm text-zinc-400">Carga un PDF o crea una factura para activar KPI financieros.</p>
                    </Link>

                    <Link href="/flota" className="dashboard-bento group p-5 transition hover:border-emerald-500/50">
                      <div className="mb-3 inline-flex rounded-lg bg-emerald-500/15 p-2 text-emerald-400">
                        <Truck className="h-5 w-5" />
                      </div>
                      <h3 className="text-base font-semibold text-zinc-100">Configurar Flota</h3>
                      <p className="mt-1 text-sm text-zinc-400">Añade tus vehículos para estimar coste/km y emisiones reales.</p>
                    </Link>

                    <Link
                      href="/radar"
                      aria-disabled={radarLocked}
                      onClick={(event) => {
                        if (radarLocked) event.preventDefault();
                      }}
                      className={`dashboard-bento group p-5 transition ${
                        radarLocked ? "cursor-not-allowed border-zinc-800/70 opacity-75" : "hover:border-emerald-500/50"
                      }`}
                    >
                      <div className="mb-3 inline-flex rounded-lg bg-zinc-800 p-2 text-zinc-300">
                        {radarLocked ? <Lock className="h-5 w-5" /> : <Sparkles className="h-5 w-5 text-emerald-400" />}
                      </div>
                      <h3 className="text-base font-semibold text-zinc-100">Ver Radar de Vampiros</h3>
                      <p className="mt-1 text-sm text-zinc-400">
                        {radarLocked
                          ? "Bloqueado hasta subir tu primer dato operativo."
                          : "Analiza márgenes y detecta fugas de rentabilidad."}
                      </p>
                    </Link>
                  </DashboardMotionFadeIn>
                </>
              ) : (
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
              )}
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
