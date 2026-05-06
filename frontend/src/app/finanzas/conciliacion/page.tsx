"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  CheckCircle2,
  GitCompare,
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import {
  getSugerenciasPendientes,
  postConciliarAi,
  postConfirmarSugerencia,
  type MovimientoSugeridoConciliacion,
} from "@/lib/api";
import { userFacingFetchFailureMessage } from "@/lib/api-base";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-[220px] flex-col rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700/80 dark:bg-gradient-to-br dark:from-zinc-900 dark:to-zinc-950">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-500">{title}</p>
      <div className="flex-1 text-zinc-800 dark:text-zinc-100">{children}</div>
    </div>
  );
}

function SugerenciaRow({
  row,
  busy,
  onAprobar,
  onRechazar,
}: {
  row: MovimientoSugeridoConciliacion;
  busy: boolean;
  onAprobar: () => void;
  onRechazar: () => void;
}) {
  const conf = row.confidence_score;
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50 dark:border-zinc-700/60 dark:bg-zinc-950/90">
      <div className="grid grid-cols-1 gap-px bg-zinc-200 dark:bg-zinc-800/50 lg:grid-cols-2">
        <Panel title="Movimiento bancario">
          <p className="mb-1 text-sm text-zinc-500 dark:text-zinc-400">{row.fecha}</p>
          <p className="mb-2 text-lg font-semibold text-zinc-900 dark:text-white">{formatEUR(row.importe)}</p>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {row.concepto || "—"}
          </p>
          {row.iban_origen ? (
            <p className="mt-3 break-all font-mono text-xs text-zinc-500 dark:text-zinc-500">
              IBAN: {row.iban_origen}
            </p>
          ) : null}
        </Panel>

        <Panel title="Factura sugerida (IA)">
          <div className="flex flex-wrap items-start gap-2 mb-3">
            {conf != null && (
              <span
                className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold tabular-nums"
                style={{
                  background: "rgba(16, 185, 129, 0.15)",
                  color: "#34d399",
                  border: "1px solid rgba(16, 185, 129, 0.35)",
                }}
              >
                Confianza {(conf * 100).toFixed(0)}%
              </span>
            )}
            {row.factura_numero ? (
              <span className="text-sm text-zinc-500 dark:text-zinc-400">N.º {row.factura_numero}</span>
            ) : null}
          </div>
          {row.cliente_nombre ? (
            <p className="mb-1 font-medium text-zinc-900 dark:text-white">{row.cliente_nombre}</p>
          ) : null}
          <p className="mb-1 text-lg font-semibold text-emerald-700 dark:text-emerald-100">
            {row.factura_total != null ? formatEUR(row.factura_total) : "—"}
          </p>
          {row.factura_fecha ? (
            <p className="mb-3 text-xs text-zinc-500 dark:text-zinc-500">Emisión {row.factura_fecha}</p>
          ) : null}
          {row.razonamiento_ia ? (
            <p className="border-l-2 border-emerald-500/40 py-1 pl-3 text-sm text-zinc-600 dark:text-zinc-400">
              {row.razonamiento_ia}
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              disabled={busy}
              onClick={onAprobar}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2"
            >
              {busy ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              Aprobar
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onRechazar}
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-semibold text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-800/80 dark:text-zinc-200 dark:hover:bg-zinc-700"
            >
              <XCircle className="w-4 h-4" />
              Rechazar
            </button>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export default function ConciliacionPage() {
  const [items, setItems] = useState<MovimientoSugeridoConciliacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [lastAi, setLastAi] = useState<{ guardadas: number } | null>(null);
  const [actingId, setActingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const rows = await getSugerenciasPendientes();
      setItems(rows);
    } catch (e) {
      setError(userFacingFetchFailureMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runAi() {
    setLlmLoading(true);
    setError(null);
    setLastAi(null);
    try {
      const out = await postConciliarAi();
      setLastAi({ guardadas: out.sugerencias_guardadas });
      await load();
    } catch (e) {
      setError(userFacingFetchFailureMessage(e));
    } finally {
      setLlmLoading(false);
    }
  }

  async function actuar(movimiento_id: string, aprobar: boolean) {
    setActingId(movimiento_id);
    setError(null);
    try {
      await postConfirmarSugerencia(movimiento_id, aprobar);
      await load();
    } catch (e) {
      setError(userFacingFetchFailureMessage(e));
    } finally {
      setActingId(null);
    }
  }

  return (
    <AppShell active="conciliacion">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="p-8">
            <p className="text-zinc-600 dark:text-zinc-400">
              Acceso restringido: la conciliación bancaria solo está disponible para el rol
              administrador.
            </p>
          </main>
        }
      >
        <header className="ab-header z-10 flex h-16 shrink-0 items-center justify-between border-b border-zinc-200 bg-white/95 px-8 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/90">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              <GitCompare className="h-7 w-7 text-emerald-600 dark:text-emerald-400" />
              Conciliación bancaria (IA)
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Revisa emparejamientos sugeridos antes de marcar cobros</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="inline-flex items-center gap-2 text-sm font-semibold text-zinc-600 hover:text-zinc-900 disabled:opacity-50 dark:text-zinc-400 dark:hover:text-white"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Actualizar
            </button>
            <button
              type="button"
              onClick={() => void runAi()}
              disabled={llmLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-900/20 hover:bg-blue-700 disabled:opacity-50 dark:shadow-blue-950/40"
            >
              {llmLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              Generar sugerencias IA
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(37,99,235,0.08),#fafafa)] p-8 dark:bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(37,99,235,0.16),#09090b)]">
          {error && (
            <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900/45 dark:bg-red-950/35 dark:text-red-100">
              {error}
            </div>
          )}

          {lastAi && (
            <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-950/30 dark:text-emerald-100">
              Sugerencias guardadas: {lastAi.guardadas}
            </div>
          )}

          {loading && items.length === 0 ? (
            <div className="flex items-center justify-center py-24 text-zinc-500 dark:text-zinc-400">
              <Loader2 className="w-8 h-8 animate-spin mr-2" />
              Cargando…
            </div>
          ) : items.length === 0 ? (
            <div className="mx-auto max-w-xl rounded-2xl border border-dashed border-zinc-300 p-12 text-center text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
              No hay movimientos en estado <strong className="text-zinc-800 dark:text-zinc-300">Sugerido</strong>.
              Importa movimientos pendientes y pulsa{" "}
              <strong className="text-zinc-900 dark:text-zinc-200">Generar sugerencias IA</strong> para obtener
              emparejamientos.
            </div>
          ) : (
            <div className="space-y-8 max-w-6xl mx-auto">
              {items.map((row) => (
                <SugerenciaRow
                  key={row.movimiento_id}
                  row={row}
                  busy={actingId === row.movimiento_id}
                  onAprobar={() => void actuar(row.movimiento_id, true)}
                  onRechazar={() => void actuar(row.movimiento_id, false)}
                />
              ))}
            </div>
          )}
        </main>
      </RoleGuard>
    </AppShell>
  );
}
