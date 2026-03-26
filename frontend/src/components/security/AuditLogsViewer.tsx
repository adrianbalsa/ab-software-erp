"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Database,
  FileWarning,
  GitCompare,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";

import { API_BASE, authHeaders, parseApiError } from "@/lib/api";

type AuditAction = "INSERT" | "UPDATE" | "DELETE";

export type AuditLogRow = {
  id: string;
  empresa_id: string;
  table_name: string;
  record_id: string;
  action: AuditAction;
  old_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  changed_by: string | null;
  created_at: string;
};

type FieldChange = { field: string; from: unknown; to: unknown };

function stableStringify(v: unknown): string {
  if (v === null || v === undefined) return String(v);
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  return JSON.stringify(v);
}

export function computeFieldChanges(
  oldData: Record<string, unknown> | null,
  newData: Record<string, unknown> | null,
): FieldChange[] {
  if (!oldData || !newData) return [];
  const keys = new Set([...Object.keys(oldData), ...Object.keys(newData)]);
  const skip = new Set(["updated_at", "created_at"]);
  const out: FieldChange[] = [];
  for (const k of keys) {
    if (skip.has(k)) continue;
    if (stableStringify(oldData[k]) !== stableStringify(newData[k])) {
      out.push({ field: k, from: oldData[k], to: newData[k] });
    }
  }
  return out.sort((a, b) => a.field.localeCompare(b.field));
}

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("es-ES", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return String(v);
  }
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

const TABLE_FILTERS: { label: string; value: string | null }[] = [
  { label: "Todas", value: null },
  { label: "portes", value: "portes" },
  { label: "facturas", value: "facturas" },
  { label: "gastos", value: "gastos" },
];

function actionStyle(action: AuditAction): { label: string; className: string; Icon: typeof Plus } {
  switch (action) {
    case "INSERT":
      return {
        label: "Alta",
        className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
        Icon: Plus,
      };
    case "UPDATE":
      return {
        label: "Cambio",
        className: "bg-amber-500/15 text-amber-200 border-amber-500/35",
        Icon: GitCompare,
      };
    case "DELETE":
      return {
        label: "Baja",
        className: "bg-red-500/15 text-red-300 border-red-500/35",
        Icon: Trash2,
      };
    default:
      return {
        label: action,
        className: "bg-slate-500/20 text-slate-300 border-slate-500/30",
        Icon: FileWarning,
      };
  }
}

export function AuditLogsViewer() {
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tableFilter, setTableFilter] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "150");
      if (tableFilter) params.set("table_name", tableFilter);
      const res = await fetch(`${API_BASE}/api/v1/audit-logs?${params}`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        throw new Error(await parseApiError(res));
      }
      setRows((await res.json()) as AuditLogRow[]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [tableFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section
      className="rounded-2xl border border-slate-700/80 overflow-hidden shadow-xl"
      style={{
        background: "linear-gradient(165deg, #0f172a 0%, #020617 55%, #0a0f1a 100%)",
      }}
    >
      <div className="px-6 py-4 flex flex-wrap items-center justify-between gap-4 border-b border-slate-700/70 bg-slate-900/50">
        <div className="flex items-center gap-3 min-w-0">
          <div className="rounded-xl p-2.5 bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
            <History className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-slate-100 tracking-tight">
              Audit log
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Cambios en portes, facturas y gastos · solo lectura
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      <div className="px-6 py-3 flex flex-wrap gap-2 border-b border-slate-800/80 bg-slate-950/40">
        {TABLE_FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setTableFilter(f.value)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition border ${
              tableFilter === f.value
                ? "bg-indigo-500/25 text-indigo-200 border-indigo-400/40"
                : "bg-slate-900/80 text-slate-400 border-slate-700 hover:border-slate-600"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="p-6">
        {error && (
          <div className="mb-4 rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
            Cargando historial…
          </div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-12">
            No hay entradas de auditoría todavía, o aún no se aplicó la migración en Supabase.
          </p>
        ) : (
          <div className="space-y-4 max-h-[min(70vh,520px)] overflow-y-auto pr-1">
            {rows.map((row) => {
              const changes =
                row.action === "UPDATE"
                  ? computeFieldChanges(row.old_data, row.new_data)
                  : [];
              const ast = actionStyle(row.action);
              const Icon = ast.Icon;
              return (
                <article
                  key={row.id}
                  className="rounded-xl border border-slate-700/60 bg-slate-900/35 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-bold shrink-0 ${ast.className}`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {ast.label}
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
                          <Database className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                          <span className="font-mono text-indigo-200/90">{row.table_name}</span>
                          <span className="text-slate-600">·</span>
                          <span className="font-mono text-xs text-slate-400 truncate" title={row.record_id}>
                            {row.record_id}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1.5">
                          {formatWhen(row.created_at)}
                          {row.changed_by ? (
                            <>
                              {" "}
                              · actor{" "}
                              <span className="font-mono text-slate-400">{row.changed_by.slice(0, 8)}…</span>
                            </>
                          ) : (
                            <span className="text-slate-600"> · sistema / service role</span>
                          )}
                        </p>
                      </div>
                    </div>
                  </div>

                  {row.action === "INSERT" && row.new_data && (
                    <p className="mt-3 text-xs text-slate-500">
                      Registro creado ({Object.keys(row.new_data).length} campos)
                    </p>
                  )}
                  {row.action === "DELETE" && row.old_data && (
                    <p className="mt-3 text-xs text-slate-500">
                      Registro eliminado ({Object.keys(row.old_data).length} campos en copia)
                    </p>
                  )}

                  {changes.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 flex items-center gap-1.5">
                        <GitCompare className="w-3.5 h-3.5" />
                        Campos modificados
                      </p>
                      <ul className="space-y-2">
                        {changes.map((c) => (
                          <li
                            key={c.field}
                            className="rounded-lg border border-slate-700/50 bg-slate-950/40 px-3 py-2 text-xs"
                          >
                            <span className="font-mono text-indigo-300/90">{c.field}</span>
                            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-slate-300">
                              <span className="line-through decoration-slate-600 text-red-300/80 break-all max-w-[45%]">
                                {formatValue(c.from)}
                              </span>
                              <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                              <span className="text-emerald-300/95 font-medium break-all max-w-[45%]">
                                {formatValue(c.to)}
                              </span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
