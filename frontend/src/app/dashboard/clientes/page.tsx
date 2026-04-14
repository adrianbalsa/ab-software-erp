"use client";

import { type ComponentType, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CreditCard, Loader2, Send, Users, User } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { OnboardingStatusBadge } from "@/components/dashboard/OnboardingStatusBadge";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
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
    slate: "border-zinc-700 bg-zinc-900/60 text-zinc-300",
    amber: "border-amber-500/35 bg-amber-950/40 text-amber-300",
    blue: "border-emerald-500/35 bg-emerald-950/40 text-emerald-400",
    emerald: "border-emerald-500/40 bg-emerald-950/50 text-emerald-400",
  } as const;
  const Icon = icon;
  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 backdrop-blur-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-400">{title}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-zinc-100">{value}</p>
        </div>
        <div className={`rounded-lg border p-2.5 ${tones[tone]}`}>
          <Icon className="h-5 w-5" aria-hidden />
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
    <div className="mx-auto w-full max-w-7xl bg-zinc-950 p-6 md:p-8">
      <ToastHost toast={toast} onDismiss={() => setToast(null)} durationMs={5200} />
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Onboarding Comercial de Clientes</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Seguimiento del embudo: invitación, aceptación de riesgo y activación SEPA.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/40 py-16 text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden />
          Cargando dashboard de onboarding…
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-500/35 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">
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
                    ? "bg-emerald-600 text-zinc-950 shadow-sm"
                    : "border border-zinc-700 bg-zinc-900/40 text-zinc-400 hover:border-zinc-600 hover:bg-zinc-800/40 hover:text-zinc-200"
                }`}
              >
                {tab}
              </button>
            ))}
          </section>

          <section className="mt-4 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
            <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-3">
              <h2 className="text-sm font-semibold text-zinc-100">Listado General de Clientes</h2>
              <span className="text-xs font-medium text-zinc-500">{rows.length} cliente(s) listados</span>
            </div>
            <div className="w-full overflow-x-auto">
              <table className="w-full min-w-0 text-left text-sm md:min-w-[860px]">
                <thead>
                  <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                    <th className="px-5 py-3 font-semibold">Cliente</th>
                    <th className="px-5 py-3 font-semibold">Email</th>
                    <th className="hidden px-5 py-3 font-semibold md:table-cell">Fecha invitación</th>
                    <th className="px-5 py-3 font-semibold">Límite de crédito</th>
                    <th className="px-5 py-3 font-semibold">Estado</th>
                    <th className="px-5 py-3 text-right font-semibold">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-zinc-500">
                        No hay clientes para monitorizar en este tenant.
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id} className="transition-colors hover:bg-zinc-800/30">
                        <td className="px-5 py-3 font-medium text-zinc-100">{row.nombre || "—"}</td>
                        <td className="max-w-[min(100vw,14rem)] px-5 py-3 md:max-w-none">
                          <div className="truncate text-zinc-300" title={row.email || undefined}>
                            {row.email || "—"}
                          </div>
                        </td>
                        <td className="hidden px-5 py-3 text-zinc-400 md:table-cell">
                          {getDaysAgo(row.fecha_invitacion)}
                        </td>
                        <td className="px-5 py-3 text-zinc-300">{formatEUR(row.limite_credito ?? 0)}</td>
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
                                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900/60 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:cursor-not-allowed disabled:opacity-60"
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
                              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900/60 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:border-emerald-500/50 hover:text-emerald-400"
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
