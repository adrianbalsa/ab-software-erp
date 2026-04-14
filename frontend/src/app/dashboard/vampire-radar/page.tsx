"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bot, Loader2, Send, X } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { VampireMap } from "@/components/maps/VampireMap";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, streamAdvisorAsk, type PorteListRow } from "@/lib/api";

const COST_EUR_PER_KM = 0.62;

type RadarPorte = PorteListRow & {
  efficiency_eta: number | null;
};

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
};

function formatEUR(value: number) {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNum(value: number, max = 2) {
  return new Intl.NumberFormat("es-ES", {
    minimumFractionDigits: 0,
    maximumFractionDigits: max,
  }).format(value);
}

function statusMeta(eta: number | null): { label: string; variant: "destructive" | "warning" | "success"; tone: string } {
  if (eta == null) {
    return {
      label: "Sin ETA",
      variant: "warning",
      tone: "text-amber-200",
    };
  }
  if (eta < 1.15) {
    return {
      label: "Vampiro",
      variant: "destructive",
      tone: "text-red-300",
    };
  }
  if (eta <= 1.3) {
    return {
      label: "Margen Ajustado",
      variant: "warning",
      tone: "text-amber-300",
    };
  }
  return {
    label: "Rentable",
    variant: "success",
    tone: "text-emerald-300",
  };
}

function estimateCost(km: number) {
  return km * COST_EUR_PER_KM;
}

const ACTIVE_STATES = new Set(["pendiente", "asignado", "en_ruta", "cargando", "en_transito", "activo"]);

export default function VampireRadarPage() {
  const [portes, setPortes] = useState<RadarPorte[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<RadarPorte | null>(null);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.portes.list();
      const active = (rows ?? []).filter((r) => ACTIVE_STATES.has(String(r.estado ?? "").toLowerCase()));
      const normalized = active.map((row) => {
        const raw = row as PorteListRow & { efficiency_eta?: unknown };
        return {
          ...row,
          efficiency_eta: typeof raw.efficiency_eta === "number" ? raw.efficiency_eta : null,
        };
      });
      setPortes(normalized);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los portes activos");
      setPortes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rows = portes;

  const leak = useMemo(() => {
    return rows.reduce((acc, row) => {
      const ingreso = Number(row.precio_pactado ?? 0);
      const coste = estimateCost(Number(row.km_estimados ?? 0));
      const margin = ingreso - coste;
      return margin < 0 ? acc + Math.abs(margin) : acc;
    }, 0);
  }, [rows]);

  const pieData = useMemo(() => {
    let rentable = 0;
    let vampiro = 0;
    for (const row of rows) {
      const eta = row.efficiency_eta;
      if (eta == null) continue;
      if (eta < 1.15) vampiro += 1;
      else if (eta > 1.3) rentable += 1;
    }
    return [
      { name: "Rentable", value: rentable, color: "#10b981" },
      { name: "Vampiros", value: vampiro, color: "#ef4444" },
    ];
  }, [rows]);

  const openAdvisor = (route: RadarPorte) => {
    setSelectedRoute(route);
    setMessages([]);
    setChatInput(
      `Analiza esta ruta ${route.origen} -> ${route.destino}. Dame diagnóstico breve, causa raíz y 3 acciones tácticas para mejorar margen.`,
    );
    setChatError(null);
  };

  const sendAdvisorPrompt = async () => {
    const text = chatInput.trim();
    if (!selectedRoute || !text || streaming) return;

    const context = [
      `Ruta: ${selectedRoute.origen} -> ${selectedRoute.destino}`,
      `Ingresos: ${formatEUR(Number(selectedRoute.precio_pactado ?? 0))}`,
      `Km: ${formatNum(Number(selectedRoute.km_estimados ?? 0), 1)}`,
      `Coste estimado: ${formatEUR(estimateCost(Number(selectedRoute.km_estimados ?? 0)))}`,
      `Eficiencia eta: ${selectedRoute.efficiency_eta == null ? "N/D" : formatNum(selectedRoute.efficiency_eta, 2)}`,
      `Estado: ${selectedRoute.estado}`,
    ].join("\n");

    const finalPrompt = `${text}\n\nContexto operativo:\n${context}`;
    setChatInput("");
    setChatError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      await streamAdvisorAsk(
        { message: finalPrompt, stream: true },
        {
          onDelta: (chunk) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { role: "assistant", content: last.content + chunk };
              }
              return next;
            });
          },
          onError: (msg) => {
            setChatError(msg);
            setMessages((prev) => (prev.length >= 2 ? prev.slice(0, -2) : prev));
          },
        },
      );
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "No se pudo consultar LogisAdvisor");
      setMessages((prev) => (prev.length >= 2 ? prev.slice(0, -2) : prev));
    } finally {
      setStreaming(false);
    }
  };

  return (
    <AppShell active="vampire_radar">
      <RoleGuard allowedRoles={["owner", "admin", "traffic_manager"]}>
        <main className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-zinc-950">
          <header className="flex min-h-16 shrink-0 items-center justify-between border-b border-zinc-800 bg-zinc-950/90 px-4 py-3 backdrop-blur-md sm:px-6">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Vampire Radar</h1>
              <p className="mt-0.5 text-xs text-zinc-500">Detección quirúrgica de fugas de margen por ruta activa.</p>
            </div>
            <Button variant="outline" className="border-zinc-700 bg-zinc-900 text-zinc-100 hover:bg-zinc-800" onClick={() => void refresh()}>
              Actualizar
            </Button>
          </header>

          <div className="mx-auto grid w-full max-w-[1600px] gap-6 p-4 sm:p-6">
            <Card className="border-zinc-800 bg-gradient-to-br from-zinc-900/95 to-zinc-950">
              <CardHeader className="pb-2">
                <CardTitle className="text-zinc-100">Daily Margin Leak</CardTitle>
                <CardDescription className="text-zinc-400">Suma de márgenes negativos en portes activos.</CardDescription>
              </CardHeader>
              <CardContent className="flex items-end justify-between gap-4">
                <p className="text-3xl font-bold tracking-tight text-red-300">{formatEUR(leak)}</p>
                <span className="text-xs text-zinc-500">{rows.length} rutas monitorizadas</span>
              </CardContent>
            </Card>

            <Card className="border-zinc-800 bg-zinc-900/60">
              <CardHeader>
                <CardTitle className="text-zinc-100">Mapa de rentabilidad por ruta</CardTitle>
                <CardDescription className="text-zinc-400">
                  Líneas verdes: eficiencia {">"} 90 %. Rojas: {"<"} 70 % (vampiros). Pasa el cursor para EBITDA
                  estimado.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0 sm:px-6">
                <VampireMap portes={rows} className="relative h-[min(420px,55vh)] w-full min-h-[300px] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 sm:rounded-lg" />
              </CardContent>
            </Card>

            <Card className="border-zinc-800 bg-zinc-900/60">
              <CardHeader>
                <CardTitle className="text-zinc-100">Distribución Rentable vs Vampiros</CardTitle>
                <CardDescription className="text-zinc-400">Relación de rutas sanas frente a rutas con sangrado de margen.</CardDescription>
              </CardHeader>
              <CardContent className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={76} stroke="none" label={({ name, value }) => `${name}: ${value}`}>
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value) => [`${value ?? ""}`, "Rutas"]}
                      contentStyle={{
                        backgroundColor: "#09090b",
                        border: "1px solid #27272a",
                        borderRadius: 12,
                        color: "#f4f4f5",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="border-zinc-800 bg-zinc-900/60">
              <CardHeader>
                <CardTitle className="text-zinc-100">Rutas activas en vigilancia</CardTitle>
                <CardDescription className="text-zinc-400">
                  Umbrales η: Vampiro &lt; 1.15 · Margen Ajustado 1.15–1.30 · Rentable &gt; 1.30.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-400">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Cargando portes activos...
                  </div>
                ) : error ? (
                  <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                    {error}
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Ruta</TableHead>
                        <TableHead className="text-right">Income (€)</TableHead>
                        <TableHead className="text-right">Est. Cost (€)</TableHead>
                        <TableHead className="text-right">Efficiency (η)</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Acción</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((row) => {
                        const ingreso = Number(row.precio_pactado ?? 0);
                        const coste = estimateCost(Number(row.km_estimados ?? 0));
                        const meta = statusMeta(row.efficiency_eta);
                        return (
                          <TableRow key={row.id}>
                            <TableCell className="font-medium text-zinc-100">
                              {row.origen} - {row.destino}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">{formatEUR(ingreso)}</TableCell>
                            <TableCell className="text-right tabular-nums">{formatEUR(coste)}</TableCell>
                            <TableCell className={`text-right font-mono ${meta.tone}`}>
                              {row.efficiency_eta == null ? "N/D" : formatNum(row.efficiency_eta, 2)}
                            </TableCell>
                            <TableCell>
                              <Badge variant={meta.variant}>{meta.label}</Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                size="sm"
                                variant="outline"
                                className="border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800"
                                onClick={() => openAdvisor(row)}
                              >
                                Consultar IA
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </main>

        {selectedRoute ? (
          <>
            <button
              type="button"
              className="fixed inset-0 z-[60] bg-black/55"
              aria-label="Cerrar panel de LogisAdvisor"
              onClick={() => setSelectedRoute(null)}
            />
            <aside className="fixed inset-y-0 right-0 z-[70] flex w-[min(100vw,28rem)] flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl">
              <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/15 p-1.5">
                    <Bot className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-zinc-100">LogisAdvisor</p>
                    <p className="text-xs text-zinc-500">
                      {selectedRoute.origen} - {selectedRoute.destino}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setSelectedRoute(null)} className="text-zinc-400 hover:text-zinc-100">
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto px-3 py-4">
                {messages.length === 0 ? (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3 text-xs text-zinc-400">
                    Consulta sugerida: explica por qué la eficiencia de esta ruta cae y qué palancas tácticas activar esta semana.
                  </div>
                ) : null}
                {messages.map((m, idx) => (
                  <div key={`${m.role}-${idx}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[92%] rounded-xl px-3 py-2 text-sm ${
                        m.role === "user"
                          ? "bg-emerald-600 text-white"
                          : "border border-zinc-700 bg-zinc-900 text-zinc-100"
                      }`}
                    >
                      {m.content || (streaming && m.role === "assistant" ? "Analizando..." : "")}
                    </div>
                  </div>
                ))}
                {chatError ? (
                  <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-200">
                    <span className="inline-flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      {chatError}
                    </span>
                  </div>
                ) : null}
              </div>

              <div className="border-t border-zinc-800 p-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        void sendAdvisorPrompt();
                      }
                    }}
                    placeholder="Pregunta táctica para esta ruta..."
                    className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                    disabled={streaming}
                  />
                  <Button onClick={() => void sendAdvisorPrompt()} disabled={streaming || !chatInput.trim()} className="bg-emerald-600 hover:bg-emerald-500">
                    {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </aside>
          </>
        ) : null}
      </RoleGuard>
    </AppShell>
  );
}
