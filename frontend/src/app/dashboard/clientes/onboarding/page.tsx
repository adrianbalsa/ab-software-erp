"use client";

import { type ComponentType, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CreditCard, Loader2, Users } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import {
  fetchClientesOnboardingDashboard,
  type OnboardingDashboardData,
  type OnboardingDashboardRow,
} from "@/lib/api";

function formatEUR(value: number): string {
  return value.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

function StatusBadge({ estado }: { estado: OnboardingDashboardRow["estado"] }) {
  if (estado === "ACTIVE") {
    return (
      <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
        100% Operativo
      </span>
    );
  }
  if (estado === "PENDING_SEPA") {
    return (
      <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
        Falta Mandato SEPA
      </span>
    );
  }
  return (
    <span className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
      Evaluación Pendiente
    </span>
  );
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

  const rows = useMemo(() => data?.clientes ?? [], [data]);
  const summary = data?.summary;

  return (
    <div className="mx-auto w-full max-w-7xl p-6 md:p-8">
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

          <section className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-800">Tabla de control de onboarding</h2>
            </div>
            <div className="w-full overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/80 text-slate-600">
                    <th className="px-5 py-3 font-semibold">Cliente</th>
                    <th className="px-5 py-3 font-semibold">Email</th>
                    <th className="px-5 py-3 font-semibold">Límite de crédito</th>
                    <th className="px-5 py-3 font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-8 text-center text-slate-500">
                        No hay clientes para monitorizar en este tenant.
                      </td>
                    </tr>
                  ) : (
                    rows.map((row) => (
                      <tr key={row.id} className="hover:bg-slate-50/60">
                        <td className="px-5 py-3 font-medium text-slate-900">{row.nombre || "—"}</td>
                        <td className="px-5 py-3 text-slate-700">{row.email || "—"}</td>
                        <td className="px-5 py-3 text-slate-700">{formatEUR(row.limite_credito ?? 0)}</td>
                        <td className="px-5 py-3">
                          <StatusBadge estado={row.estado} />
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

