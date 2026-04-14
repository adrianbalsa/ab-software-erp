"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Loader2, RefreshCw, Users } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { API_BASE, apiFetch } from "@/lib/api";

const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/25";

type ClienteRow = {
  id: string;
  nombre: string;
  nif?: string | null;
  email?: string | null;
  telefono?: string | null;
};

function ClientesContent() {
  const [rows, setRows] = useState<ClienteRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nombre, setNombre] = useState("");
  const [nif, setNif] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`${API_BASE}/clientes/`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      const data = (await res.json()) as ClienteRow[];
      setRows(data.filter((r) => r.nombre));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const crear = async () => {
    const n = nombre.trim();
    if (!n) {
      setFormError("Indica el nombre del cliente.");
      return;
    }
    setFormError(null);
    setSaving(true);
    try {
      const res = await apiFetch(`${API_BASE}/clientes/`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nombre: n,
          nif: nif.trim() || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      setNombre("");
      setNif("");
      await load();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Error al crear");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-4xl bg-zinc-950 p-6 md:p-8">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-100">
            <Users className="h-7 w-7 text-emerald-500" aria-hidden />
            Clientes
          </h1>
          <p className="mt-1 text-sm text-zinc-400">Alta y listado de clientes para portes y facturación.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/clientes"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50"
          >
            <BarChart3 className="h-4 w-4" aria-hidden />
            Dashboard Onboarding
          </Link>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/40 px-3 py-2 text-sm font-medium text-zinc-200 hover:border-zinc-600 hover:bg-zinc-800/50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden />
            Actualizar
          </button>
        </div>
      </div>

      <div className="mb-8 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <h2 className="mb-3 text-sm font-semibold text-zinc-100">Nuevo cliente</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-zinc-400">Nombre / razón social</span>
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              className={inputClass}
              placeholder="Ej. Transportes García SL"
            />
          </label>
          <label className="block text-sm">
            <span className="text-zinc-400">CIF / NIF (opcional)</span>
            <input
              value={nif}
              onChange={(e) => setNif(e.target.value)}
              className={inputClass}
              placeholder="B12345678"
            />
          </label>
        </div>
        {formError && <p className="mt-2 text-sm text-red-400">{formError}</p>}
        <button
          type="button"
          onClick={() => void crear()}
          disabled={saving}
          className="mt-4 inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-emerald-500 disabled:opacity-50"
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Guardando…
            </>
          ) : (
            "Registrar cliente"
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/35 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
        <div className="border-b border-zinc-800 bg-zinc-950/40 px-5 py-3">
          <h2 className="text-sm font-semibold text-zinc-100">Clientes activos</h2>
        </div>
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-zinc-400">
            <Loader2 className="h-5 w-5 animate-spin text-emerald-500" aria-hidden />
            Cargando…
          </div>
        ) : rows.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-zinc-500">
            Aún no hay clientes. Crea el primero arriba para usarlo en{" "}
            <Link href="/portes" className="font-medium text-emerald-500 hover:text-emerald-400 hover:underline">
              Portes
            </Link>
            .
          </p>
        ) : (
          <div className="min-w-0 w-full overflow-x-auto">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="px-5 py-3 font-semibold">Nombre / razón social</th>
                  <th className="hidden w-[40%] px-5 py-3 font-semibold md:table-cell">ID (sistema)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {rows.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-zinc-800/30">
                    <td className="align-top px-5 py-3 font-medium text-zinc-100">{r.nombre}</td>
                    <td className="hidden align-top px-5 py-3 font-mono text-xs break-all text-zinc-400 md:table-cell">
                      {r.id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ClientesPage() {
  return (
    <AppShell active="clientes">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <div className="max-w-lg bg-zinc-950 p-8">
            <p className="text-zinc-300">Esta sección solo está disponible para el perfil de administrador.</p>
            <Link href="/dashboard" className="mt-4 inline-block font-medium text-emerald-500 hover:text-emerald-400 hover:underline">
              Volver al dashboard
            </Link>
          </div>
        }
      >
        <ClientesContent />
      </RoleGuard>
    </AppShell>
  );
}
