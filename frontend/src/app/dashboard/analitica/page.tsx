"use client";

import { BarChart3 } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { CIPMatrixChart } from "@/components/dashboard/CIPMatrixChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function AnaliticaCIPPage() {
  return (
    <AppShell active="analitica">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="p-8">
            <p className="text-sm text-zinc-600">Acceso restringido: solo dirección.</p>
          </main>
        }
      >
        <main className="flex flex-1 flex-col overflow-y-auto min-h-0">
          <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8 shrink-0">
            <div>
              <h1 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
                <BarChart3 className="h-7 w-7 text-[#2563eb]" />
                Matriz CIP
              </h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Margen neto vs emisiones CO₂ por ruta (burbujas = volumen de portes).
              </p>
            </div>
          </header>

          <div className="p-8 flex-1 w-full max-w-[100vw]">
            <Card className="w-full overflow-hidden border-slate-200">
              <CardHeader>
                <CardTitle>Rentabilidad y huella por ruta</CardTitle>
                <CardDescription>
                  Verde: alto margen y baja huella relativa. Rojo: priorizar renegociación o salida.
                  Véase la guía rápida del producto (Estrella / Vampiro).
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 sm:p-6 pt-0 w-full">
                <CIPMatrixChart className="w-full" />
              </CardContent>
            </Card>
          </div>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
