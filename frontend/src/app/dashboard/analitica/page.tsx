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
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-400">Acceso restringido: solo dirección.</p>
          </main>
        }
      >
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950/90 px-8 backdrop-blur-md">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
                <BarChart3 className="h-7 w-7 text-emerald-500" aria-hidden />
                Matriz CIP
              </h1>
              <p className="mt-0.5 text-sm text-zinc-400">
                Margen neto vs emisiones CO₂ por ruta (burbujas = volumen de portes).
              </p>
            </div>
          </header>

          <div className="w-full max-w-[100vw] flex-1 p-8">
            <Card className="bunker-card overflow-hidden border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Rentabilidad y huella por ruta</CardTitle>
                <CardDescription className="text-zinc-400">
                  Verde: alto margen y baja huella relativa. Rojo: priorizar renegociación o salida. Véase la guía
                  rápida del producto (Estrella / Vampiro).
                </CardDescription>
              </CardHeader>
              <CardContent className="w-full p-4 pt-0 sm:p-6">
                <CIPMatrixChart className="w-full" />
              </CardContent>
            </Card>
          </div>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
