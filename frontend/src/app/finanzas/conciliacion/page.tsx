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
    <div
      className="rounded-xl border border-slate-700/80 p-5 flex flex-col min-h-[220px]"
      style={{
        background:
          "linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(2, 6, 23, 0.98) 100%)",
      }}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
        {title}
      </p>
      <div className="flex-1 text-slate-100">{children}</div>
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
    <div className="rounded-2xl border border-slate-700/60 overflow-hidden bg-[#020617]/80">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-slate-800/50">
        <Panel title="Movimiento bancario">
          <p className="text-sm text-slate-400 mb-1">{row.fecha}</p>
          <p className="text-lg font-semibold text-white mb-2">
            {formatEUR(row.importe)}
          </p>
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {row.concepto || "—"}
          </p>
          {row.iban_origen ? (
            <p className="mt-3 text-xs font-mono text-slate-500 break-all">
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
              <span className="text-sm text-slate-400">
                N.º {row.factura_numero}
              </span>
            ) : null}
          </div>
          {row.cliente_nombre ? (
            <p className="text-white font-medium mb-1">{row.cliente_nombre}</p>
          ) : null}
          <p className="text-lg font-semibold text-emerald-100 mb-1">
            {row.factura_total != null ? formatEUR(row.factura_total) : "—"}
          </p>
          {row.factura_fecha ? (
            <p className="text-xs text-slate-500 mb-3">Emisión {row.factura_fecha}</p>
          ) : null}
          {row.razonamiento_ia ? (
            <p className="text-sm text-slate-400 border-l-2 border-emerald-500/40 pl-3 py-1">
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
              className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/80 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-sm font-semibold px-4 py-2"
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
      setError(e instanceof Error ? e.message : "Error al cargar sugerencias");
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
      setError(e instanceof Error ? e.message : "Error en conciliación IA");
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
      setError(e instanceof Error ? e.message : "Error al confirmar");
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
            <p className="text-slate-500">
              Acceso restringido: la conciliación bancaria solo está disponible para el rol
              administrador.
            </p>
          </main>
        }
      >
        <header className="h-16 ab-header border-b border-slate-800/80 flex items-center justify-between px-8 z-10 shrink-0 bg-[#0a0f1a]/90 backdrop-blur-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2">
              <GitCompare className="w-7 h-7 text-emerald-400" />
              Conciliación bancaria (IA)
            </h1>
            <p className="text-sm text-slate-500">
              Revisa emparejamientos sugeridos antes de marcar cobros
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="inline-flex items-center gap-2 text-sm font-semibold text-slate-300 hover:text-white disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              Actualizar
            </button>
            <button
              type="button"
              onClick={() => void runAi()}
              disabled={llmLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5 shadow-lg shadow-blue-900/30"
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

        <main
          className="p-8 flex-1 overflow-y-auto min-h-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(37, 99, 235, 0.12), transparent), #020617",
          }}
        >
          {error && (
            <div
              className="mb-6 rounded-xl border px-4 py-3 text-sm text-red-200"
              style={{
                background: "rgba(127, 29, 29, 0.25)",
                borderColor: "rgba(248, 113, 113, 0.35)",
              }}
            >
              {error}
            </div>
          )}

          {lastAi && (
            <div
              className="mb-6 rounded-xl border border-emerald-500/30 px-4 py-3 text-sm text-emerald-100"
              style={{ background: "rgba(6, 78, 59, 0.25)" }}
            >
              Sugerencias guardadas: {lastAi.guardadas}
            </div>
          )}

          {loading && items.length === 0 ? (
            <div className="flex items-center justify-center py-24 text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin mr-2" />
              Cargando…
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-slate-500 max-w-xl mx-auto">
              No hay movimientos en estado <strong className="text-slate-400">Sugerido</strong>.
              Importa movimientos pendientes y pulsa{" "}
              <strong className="text-slate-300">Generar sugerencias IA</strong> para obtener
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
