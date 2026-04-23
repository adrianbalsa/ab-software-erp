"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { jwtRbacRole, type AppRbacRole } from "@/lib/api";

function targetForRole(role: AppRbacRole): string {
  if (role === "owner" || role === "traffic_manager") return "/sostenibilidad/auditoria";
  if (role === "cliente") return "/portal-cliente/sostenibilidad";
  return "/dashboard";
}

export default function SostenibilidadPage() {
  const router = useRouter();

  useEffect(() => {
    const target = targetForRole(jwtRbacRole());
    router.replace(target);
  }, [router]);

  return (
    <AppShell active="sostenibilidad">
      <div className="mx-auto mt-10 max-w-3xl rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
        <h1 className="text-xl font-semibold text-zinc-100">Sostenibilidad ESG</h1>
        <p className="mt-2 text-sm text-zinc-400">
          Redirigiendo al módulo ESG correspondiente según tu perfil de acceso.
        </p>
      </div>
    </AppShell>
  );
}

