"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Calculator, Loader2, RefreshCw } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { useDebounce } from "@/hooks/useDebounce";
import { api, type SimulationInput, type SimulationResult } from "@/lib/api";

const SIM_DEBOUNCE_MS = 450;

function formatEUR(value: number): string {
  return value.toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}

function fmtPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("es-ES", { maximumFractionDigits: 2 })}%`;
}

export default function SimuladorImpactoPage() {
  const [combustible, setCombustible] = useState(0);
  const [salarios, setSalarios] = useState(0);
  const [peajes, setPeajes] = useState(0);
  const debouncedCombustible = useDebounce(combustible, SIM_DEBOUNCE_MS);
  const debouncedSalarios = useDebounce(salarios, SIM_DEBOUNCE_MS);
  const debouncedPeajes = useDebounce(peajes, SIM_DEBOUNCE_MS);

  const simReqId = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);

  const runSimulationRequest = useCallback(async (input: SimulationInput) => {
    const id = ++simReqId.current;
    setLoading(true);
    setError(null);
    try {
      const res = await api.analytics.simulateImpact(input);
      if (id !== simReqId.current) return;
      setResult(res);
    } catch (e: unknown) {
      if (id !== simReqId.current) return;
      setError(e instanceof Error ? e.message : "No se pudo calcular la simulación");
    } finally {
      if (id === simReqId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void runSimulationRequest({
      cambio_combustible_pct: debouncedCombustible,
      cambio_salarios_pct: debouncedSalarios,
      cambio_peajes_pct: debouncedPeajes,
    });
  }, [debouncedCombustible, debouncedSalarios, debouncedPeajes, runSimulationRequest]);

  const chartData = useMemo(() => {
    if (!result) return [];
    return [
      { escenario: "Actual", ebitda: result.ebitda_base_eur },
      { escenario: "Simulado", ebitda: result.ebitda_simulado_eur },
    ];
  }, [result]);

  return (
    <AppShell active="simulador">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="bg-zinc-950 p-8">
            <p className="text-sm text-zinc-400">Acceso restringido: solo dirección.</p>
          </main>
        }
      >
        <main className="space-y-6 bg-zinc-950 p-8">
          <header>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
              <Calculator className="h-6 w-6 text-emerald-500" aria-hidden />
              Simulador de Impacto Económico
            </h1>
            <p className="mt-1 text-sm text-zinc-400">
              Analiza sensibilidad de margen frente a variaciones de combustible, salarios y peajes.
            </p>
          </header>

          <Card className="bunker-card">
            <CardHeader>
              <CardTitle className="text-zinc-100">Variables de simulación</CardTitle>
              <CardDescription className="text-zinc-400">
                Ajusta los costes y recalcula el EBITDA esperado.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-zinc-300">Cambio combustible</span>
                  <span className="text-zinc-400">{fmtPct(combustible)}</span>
                </div>
                <Slider value={[combustible]} min={-30} max={50} step={1} onValueChange={(v) => setCombustible(v[0] ?? 0)} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-zinc-300">Cambio salarios</span>
                  <span className="text-zinc-400">{fmtPct(salarios)}</span>
                </div>
                <Slider value={[salarios]} min={-30} max={50} step={1} onValueChange={(v) => setSalarios(v[0] ?? 0)} />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-zinc-300">Cambio peajes</span>
                  <span className="text-zinc-400">{fmtPct(peajes)}</span>
                </div>
                <Slider value={[peajes]} min={-30} max={50} step={1} onValueChange={(v) => setPeajes(v[0] ?? 0)} />
              </div>

              <button
                type="button"
                onClick={() =>
                  void runSimulationRequest({
                    cambio_combustible_pct: combustible,
                    cambio_salarios_pct: salarios,
                    cambio_peajes_pct: peajes,
                  })
                }
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-60"
              >
                <RefreshCw className="w-4 h-4" />
                Recalcular ahora
              </button>

              {loading ? (
                <div
                  className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-2 text-sm font-medium text-emerald-200"
                  role="status"
                  aria-live="polite"
                >
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-emerald-500" />
                  Recalculando…
                </div>
              ) : null}

              {error ? (
                <div className="rounded-md border border-rose-500/35 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
                  {error}
                </div>
              ) : null}
            </CardContent>
          </Card>

          {result ? (
            <>
              <Card className="bunker-card border-emerald-500/35">
                <CardHeader>
                  <CardDescription className="text-zinc-400">Impacto principal estimado</CardDescription>
                  <CardTitle className="text-3xl font-extrabold tracking-tight text-zinc-100">
                    Impacto estimado en beneficio:{" "}
                    <span className={result.impacto_mensual_estimado_eur <= 0 ? "text-rose-400" : "text-emerald-500"}>
                      {formatEUR(result.impacto_mensual_estimado_eur)}/mes
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm text-zinc-400">
                  <p>Impacto EBITDA periodo: {formatEUR(result.impacto_ebitda_eur)} ({fmtPct(result.impacto_ebitda_pct)})</p>
                  <p>
                    Punto de ruptura tarifario: +{result.break_even.tarifa_incremento_pct.toLocaleString("es-ES", { maximumFractionDigits: 2 })}% para mantener margen.
                  </p>
                </CardContent>
              </Card>

              <Card className="bunker-card">
                <CardHeader>
                  <CardTitle className="text-zinc-100">Situación Actual vs Simulada</CardTitle>
                  <CardDescription className="text-zinc-400">
                    Comparativa de EBITDA agregado en ventana de {result.periodo_meses} meses.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="relative h-[320px] w-full">
                    {loading ? (
                      <div
                        className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-zinc-950/50 backdrop-blur-[1px]"
                        aria-hidden
                      >
                        <span className="inline-flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900/95 px-3 py-1.5 text-xs font-medium text-zinc-200 shadow-sm">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-500" />
                          Recalculando…
                        </span>
                      </div>
                    ) : null}
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        margin={{ top: 8, right: 8, left: 8, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="escenario" />
                        <YAxis tickFormatter={(v) => `${Math.round(Number(v) / 1000)}k`} />
                        <Tooltip formatter={(value) => formatEUR(Number(value))} />
                        <Legend />
                        <Bar
                          dataKey="ebitda"
                          name="EBITDA"
                          fill="#10b981"
                          radius={[8, 8, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : null}
        </main>
      </RoleGuard>
    </AppShell>
  );
}
