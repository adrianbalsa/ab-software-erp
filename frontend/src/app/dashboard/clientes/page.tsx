"use client";

import { type ComponentType, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CreditCard, Loader2, Send, Users, User } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { OnboardingStatusBadge } from "@/components/dashboard/OnboardingStatusBadge";
import Link from "next/link";
import {
  api,
  fetchClientesOnboardingDashboard,
  type OnboardingDashboardData,
  type OnboardingDashboardRow,
} from "@/lib/api";

function formatEUR(value: number): string {
  return value.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

function getDaysAgo(dateString?: string | null): string {
  if (!dateString) return "No invitado";
  const diffTime = Math.abs(new Date().getTime() - new Date(dateString).getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Invitado hoy";
  if (diffDays === 1) return "Invitado hace 1 día";
  return `Invitado hace ${diffDays} días`;
}

function KpiCard({
  title,
  value,
  tone,
  icon,
}: {
  title: string;
  value: number;
  tone: "slate" | "amber" | "blue" | "emerald";
  icon: ComponentType<{ className?: string }>;
}) {
  const tones = {
    slate: "bg-slate-50 border-slate-200 text-slate-700",
    amber: "bg-amber-50 border-amber-200 text-amber-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-700",
  } as const;
  const Icon = icon;
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600">{title}</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
        </div>
        <div className={`rounded-lg border p-2.5 ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </article>
  );
}

function OnboardingClientesDashboardContent() {
  const [data, setData] = useState<OnboardingDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [resendingById, setResendingById] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<"Todos" | "Pendientes" | "Activos">("Todos");

  const showToast = (message: string, tone: ToastPayload["tone"]) => {
    setToast({ id: Date.now(), message, tone });
  };

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchClientesOnboardingDashboard();
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "No se pudo cargar el dashboard.");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const allRows = useMemo(() => data?.clientes ?? [], [data]);
  const rows = useMemo(() => {
    if (activeTab === "Todos") return allRows;
    if (activeTab === "Activos") return allRows.filter((r) => r.riesgo_aceptado && r.mandato_activo);
    // Pendientes
    return allRows.filter((r) => !(r.riesgo_aceptado && r.mandato_activo));
  }, [allRows, activeTab]);

  const summary = data?.summary;

  const handleResendInvite = async (row: OnboardingDashboardRow) => {
    setResendingById((prev) => ({ ...prev, [row.id]: true }));
    try {
      await api.clientes.resendInvite(row.id);
      showToast(`Invitación reenviada con éxito a ${row.nombre}.`, "success");
    } catch (e) {
      showToast(
        e instanceof Error ? e.message : "No se pudo reenviar la invitación.",
        "error",
      );
    } finally {
      setResendingById((prev) => ({ ...prev, [row.id]: false }));
    }
  };

  return (
    <div className="mx-auto w-full max-w-7xl p-6 md:p-8">
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={5200} />
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Onboarding Comercial de Clientes</h1>
        <p className="mt-1 text-sm text-slate-600">
          Seguimiento del embudo: invitación, aceptación de riesgo y activación SEPA.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-16 text-slate-600">
          <Loader2 className="h-5 w-5 animate-spin" />
          Cargando dashboard de onboarding...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : (
        <>
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <KpiCard title="Total clientes" value={summary?.total_clientes ?? 0} tone="slate" icon={Users} />
            <KpiCard
              title="Pendientes de firma"
              value={summary?.pendientes_riesgo ?? 0}
              tone="amber"
              icon={AlertTriangle}
            />
            <KpiCard
              title="Pendientes de banco"
              value={summary?.pendientes_sepa ?? 0}
              tone="blue"
              icon={CreditCard}
            />
            <KpiCard title="Operativos" value={summary?.operativos ?? 0} tone="emerald" icon={CheckCircle2} />
          </section>

          <section className="mt-6 flex gap-2">
            {(["Todos", "Pendientes", "Activos"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-slate-800 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {tab}
              </button>
            ))}
          </section>

          <section className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800">Listado General de Clientes</h2>
              <span className="text-xs font-medium text-slate-500">{rows.length} cliente(s) listados</span>
            </div>
            <div className="w-full overflow-x-auto">
              <table className="w-full min-w-0 text-left text-sm md:min-w-[860px]">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/80 text-slate-600">
                    <th className="px-5 py-3 font-semibold">Cliente</th>
                    <th className="px-5 py-3 font-semibold">Email</th>
                    <th className="hidden px-5 py-3 font-semibold md:table-cell">Fecha invitación</th>
                    <th className="px-5 py-3 font-semibold">Límite de crédito</th>
                    <th className="px-5 py-3 font-semibold">Estado</th>
                    <th className="px-5 py-3 font-semibold text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-slate-500">
                        No hay clientes para monitorizar en este tenant.
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-medium text-slate-900">{row.nombre || "—"}</td>
                        <td className="max-w-[min(100vw,14rem)] px-5 py-3 md:max-w-none">
                          <div className="truncate text-slate-700" title={row.email || undefined}>
                            {row.email || "—"}
                          </div>
                        </td>
                        <td className="hidden px-5 py-3 text-slate-600 md:table-cell">
                          {getDaysAgo(row.fecha_invitacion)}
                        </td>
                        <td className="px-5 py-3 text-slate-700">{formatEUR(row.limite_credito ?? 0)}</td>
                        <td className="px-5 py-3">
                          <OnboardingStatusBadge 
                            riesgoAceptado={row.riesgo_aceptado} 
                            mandatoActivo={row.mandato_activo} 
                            isBlocked={row.is_blocked} 
                          />
                        </td>
                        <td className="px-5 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {!(row.riesgo_aceptado && row.mandato_activo) && (
                              <button
                                type="button"
                                onClick={() => void handleResendInvite(row)}
                                disabled={Boolean(resendingById[row.id])}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                                title="Reenviar invitación"
                                aria-label={`Reenviar invitación por email a ${row.nombre || "cliente"}`}
                              >
                                {resendingById[row.id] ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Send className="h-3.5 w-3.5" />
                                )}
                                Reenviar
                              </button>
                            )}
                            <Link
                              href={`/dashboard/clientes/${row.id}`}
                              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              aria-label={`Ver perfil de ${row.nombre || "cliente"}`}
                            >
                              <User className="h-3.5 w-3.5" />
                              Ver Perfil
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default function OnboardingClientesDashboardPage() {
  return (
    <AppShell active="clientes">
      <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
        <OnboardingClientesDashboardContent />
      </RoleGuard>
    </AppShell>
  );
}

