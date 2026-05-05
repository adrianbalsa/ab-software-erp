"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ThemedToaster } from "@/components/ThemedToaster";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TourGuide } from "@/components/onboarding/TourGuide";
import { AuthProvider } from "@/context/AuthProvider";
import { LocaleProvider, useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { RoleProvider } from "@/context/RoleProvider";
import type { AppRbacRole } from "@/lib/api";
import { isSupabaseConfigured } from "@/lib/supabase";

function ConfiguracionPendienteScreen() {
  const { catalog } = useOptionalLocaleCatalog();
  const c = catalog.common;
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8">
      <section className="w-full max-w-xl rounded-2xl border border-zinc-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-2xl font-semibold text-zinc-900">{c.configPendingTitle}</h1>
        <p className="mt-3 text-sm text-zinc-600">{c.configPendingBody}</p>
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
  const [queryClient] = useState(() => new QueryClient());

  return (
    <ThemeProvider>
      <LocaleProvider>
        {!isSupabaseConfigured() ? (
          <ConfiguracionPendienteScreen />
        ) : (
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              <RoleProvider initialRole={initialRole}>
                {children}
                <TourGuide />
                <ThemedToaster />
              </RoleProvider>
            </AuthProvider>
          </QueryClientProvider>
        )}
      </LocaleProvider>
    </ThemeProvider>
  );
}
