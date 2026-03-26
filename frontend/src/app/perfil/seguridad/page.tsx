"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Laptop,
  Loader2,
  RefreshCw,
  Shield,
  Smartphone,
  Trash2,
  LogOut,
} from "lucide-react";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/AppShell";
import { AuditLogsViewer } from "@/components/security/AuditLogsViewer";
import { API_BASE, authHeaders } from "@/lib/api";

type ActiveSession = {
  id: string;
  device_type: "desktop" | "mobile";
  client_summary: string;
  ip_address: string | null;
  created_at: string;
  is_current: boolean;
};

function formatSessionDate(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 19);
    return d.toLocaleString("es-ES", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function SeguridadPage() {
  const [token, setToken] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ActiveSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [closingAll, setClosingAll] = useState(false);
  const [confirmAllOpen, setConfirmAllOpen] = useState(false);

  useEffect(() => {
    try {
      setToken(localStorage.getItem("jwt_token"));
    } catch {
      setToken(null);
    }
  }, []);

  const load = useCallback(async () => {
    if (!token) {
      setSessions([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/sessions`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      const json = (await res.json()) as ActiveSession[];
      setSessions(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const cerrarSesion = async (id: string) => {
    setActionId(id);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/sessions/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setActionId(null);
    }
  };

  const cerrarTodasLasDemas = async () => {
    setClosingAll(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/sessions/all`, {
        method: "DELETE",
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`,
        );
      }
      setConfirmAllOpen(false);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setClosingAll(false);
    }
  };

  return (
    <AppShell active="seguridad">
      <header
        className="h-16 flex items-center justify-between px-8 shrink-0 border-b border-slate-200/80"
        style={{ background: "linear-gradient(90deg, #f8fafc 0%, #eff6ff 100%)" }}
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "#0b1224" }}>
            Seguridad
          </h1>
          <p className="text-sm text-slate-500">
            Sesiones activas y control de acceso
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading || !token}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#2563eb] disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </header>

      <main className="p-8 flex-1 overflow-y-auto max-w-4xl">
        {!token && (
          <div
            className="rounded-2xl border px-4 py-6 text-sm"
            style={{ borderColor: "#2563eb40", background: "#f8fafc", color: "#0b1224" }}
          >
            Inicia sesión (por ejemplo desde <strong>Portes</strong>) para ver y gestionar tus sesiones.
          </div>
        )}

        {token && error && (
          <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {error}
          </div>
        )}

        {token && (
          <section
            className="rounded-2xl border shadow-sm overflow-hidden"
            style={{ borderColor: "#e2e8f0", background: "#fff" }}
          >
            <div
              className="px-6 py-4 flex flex-wrap items-center justify-between gap-3 border-b"
              style={{ borderColor: "#e2e8f0", background: "#f1f5f9" }}
            >
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-[#2563eb]" />
                <h2 className="font-bold text-lg" style={{ color: "#0b1224" }}>
                  Sesiones activas
                </h2>
              </div>
              <button
                type="button"
                disabled={loading || sessions.length <= 1 || closingAll}
                onClick={() => setConfirmAllOpen(true)}
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-white shadow-md transition hover:opacity-95 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: "#2563eb" }}
              >
                Cerrar todas las demás sesiones
              </button>
            </div>

            <div className="p-6">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-12 text-slate-500">
                  <Loader2 className="w-6 h-6 animate-spin text-[#2563eb]" />
                  Cargando sesiones…
                </div>
              ) : sessions.length === 0 ? (
                <p className="text-sm text-slate-500 py-6 text-center">
                  No hay sesiones activas registradas (o tu usuario no tiene fila en{" "}
                  <code className="text-xs">usuarios</code> con refresh tokens).
                </p>
              ) : (
                <ul className="space-y-3">
                  {sessions.map((s) => (
                    <li
                      key={s.id}
                      className={`rounded-xl border p-4 flex flex-wrap items-center justify-between gap-4 transition ${
                        s.is_current ? "ring-2 ring-[#2563eb]/40 bg-[#2563eb]/5" : "bg-slate-50/80"
                      }`}
                      style={{ borderColor: s.is_current ? "#2563eb55" : "#e2e8f0" }}
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className="rounded-lg p-2 shrink-0"
                          style={{ background: "#2563eb15", color: "#2563eb" }}
                        >
                          {s.device_type === "mobile" ? (
                            <Smartphone className="w-5 h-5" />
                          ) : (
                            <Laptop className="w-5 h-5" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-[#0b1224]">{s.client_summary}</p>
                          <p className="text-sm text-slate-600 mt-0.5">
                            IP:{" "}
                            <span className="font-mono text-xs">
                              {s.ip_address ?? "—"}
                            </span>
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            Inicio: {formatSessionDate(s.created_at)}
                            {s.is_current && (
                              <span
                                className="ml-2 font-semibold text-[#2563eb]"
                              >
                                · Sesión actual
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={actionId === s.id}
                        onClick={() => void cerrarSesion(s.id)}
                        className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-bold text-red-700 hover:bg-red-50 disabled:opacity-50 shrink-0"
                      >
                        {actionId === s.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <LogOut className="w-3.5 h-3.5" />
                        )}
                        Cerrar sesión
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}

        {token && (
          <RoleGuard allowedRoles={["owner"]}>
            <div className="mt-10 max-w-4xl w-full">
              <AuditLogsViewer />
            </div>
          </RoleGuard>
        )}
      </main>

      {confirmAllOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            if (e.target === e.currentTarget && !closingAll) setConfirmAllOpen(false);
          }}
        >
          <div
            className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-xl"
            style={{ borderColor: "#e2e8f0" }}
          >
            <div className="flex items-center gap-2 text-[#0b1224] font-bold text-lg">
              <Trash2 className="w-5 h-5 text-[#2563eb]" />
              Cerrar otras sesiones
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Se cerrarán todas las sesiones excepto la de este navegador. Los otros dispositivos
              tendrán que volver a iniciar sesión.
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                disabled={closingAll}
                onClick={() => setConfirmAllOpen(false)}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={closingAll}
                onClick={() => void cerrarTodasLasDemas()}
                className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-bold text-white"
                style={{ background: "#2563eb" }}
              >
                {closingAll ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : null}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
