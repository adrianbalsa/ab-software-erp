"use client";

import type { ReactNode } from "react";

import { TourGuide } from "@/components/onboarding/TourGuide";
import { AuthProvider } from "@/context/AuthProvider";
import { RoleProvider } from "@/context/RoleProvider";
import type { AppRbacRole } from "@/lib/api";
import { isSupabaseConfigured } from "@/lib/supabase";

function ConfiguracionPendienteScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <section className="w-full max-w-xl rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-2xl font-semibold text-zinc-900">Configuración pendiente</h1>
        <p className="mt-3 text-sm text-zinc-600">
          El sistema está en mantenimiento temporal. Falta completar la configuración de Supabase.
        </p>
      </section>
    </main>
  );
}

export function AppProviders({
  children,
  initialRole,
}: {
  children: ReactNode;
  initialRole?: AppRbacRole;
}) {
  if (!isSupabaseConfigured()) {
    return <ConfiguracionPendienteScreen />;
  }

  return (
    <AuthProvider>
      <RoleProvider initialRole={initialRole}>
        {children}
        <TourGuide />
      </RoleProvider>
    </AuthProvider>
  );
}
