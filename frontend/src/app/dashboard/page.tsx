"use client";

import React, { useEffect, useState } from "react";
import { TrendingUp, Package, MapPin, Euro, Bell } from "lucide-react";
import Link from "next/link";
import { AlertasCriticas } from "@/components/AlertasCriticas";
import { AppShell } from "@/components/AppShell";
import { LogisAdvisorChat } from "@/components/LogisAdvisorChat";
import { CashFlowChart } from "@/components/dashboard/CashFlowChart";
import { CostBreakdownPie } from "@/components/dashboard/CostBreakdownPie";
import { EfficiencyKpiCard } from "@/components/dashboard/EfficiencyKpiCard";
import { EconomicOverview } from "@/components/EconomicOverview";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { useFinanceDashboard } from "@/hooks/useFinanceDashboard";
import { useFleetAlerts } from "@/hooks/useFleetAlerts";

const OAUTH_WELCOME_KEY = "abl_oauth_welcome";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function Dashboard() {
  const { data, loading, error, refresh } = useFinanceDashboard();
  const {
    alerts: fleetAlerts,
    loading: fleetAlertsLoading,
    error: fleetAlertsError,
    refresh: refreshFleetAlerts,
  } = useFleetAlerts();
  const [toast, setToast] = useState<ToastPayload | null>(null);

  useEffect(() => {
    try {
      if (sessionStorage.getItem(OAUTH_WELCOME_KEY) === "1") {
        sessionStorage.removeItem(OAUTH_WELCOME_KEY);
        setToast({
          id: Date.now(),
          message: "Bienvenido",
          tone: "success",
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <AppShell active="dashboard">
      <LogisAdvisorChat />
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={5200} />
      <main className="flex-1 flex flex-col overflow-y-auto min-h-0">
        <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 z-10">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
              Cuadro de Mando Integral
            </h1>
          </div>
          <div className="flex items-center space-x-4">
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading}
              className="text-sm font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
            >
              {loading ? "Actualizando…" : "Actualizar KPIs"}
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
          {error && (
            <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-lg text-sm">
              KPI financieros: {error} (¿iniciaste sesión?).
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="ab-card p-6 rounded-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-slate-500 mb-1">
                    EBITDA (real)
                  </p>
                  <h3 className="text-3xl font-bold text-slate-800">
                    {loading
                      ? "…"
                      : data
                        ? formatEUR(data.ebitda)
                        : "—"}
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
                Bases facturadas (sin IVA) · <code className="text-xs">GET /finance/dashboard</code>
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

          <EconomicOverview />

          <AlertasCriticas
            alerts={fleetAlerts}
            loading={fleetAlertsLoading}
            error={fleetAlertsError}
            onRetry={() => void refreshFleetAlerts()}
          />

          <div className="ab-card rounded-2xl overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100/80 flex justify-between items-center bg-slate-50/50">
              <h2 className="text-lg font-bold text-slate-800">
                Accesos rápidos
              </h2>
              <div className="flex gap-4">
                <Link
                  href="/portes"
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Portes
                </Link>
                <Link
                  href="/flota"
                  className="text-sm font-medium text-[#2563eb] hover:underline"
                >
                  Flota
                </Link>
              </div>
            </div>
            <div className="p-6 text-sm text-slate-600">
              Los KPI y gráficos avanzados usan{" "}
              <code className="bg-slate-100 px-1 rounded">GET /finance/dashboard</code>{" "}
              con JWT (misma sesión que el resto de módulos).
            </div>
          </div>
        </div>
      </main>
    </AppShell>
  );
}
