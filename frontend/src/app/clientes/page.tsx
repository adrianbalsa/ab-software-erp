"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Loader2, RefreshCw, Users } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { API_BASE, apiFetch, authHeaders } from "@/lib/api";

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
      const res = await fetch(`${API_BASE}/clientes/`, {
        method: "POST",
        credentials: "include",
        headers: {
          ...authHeaders(),
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
    <div className="p-6 md:p-8 max-w-4xl mx-auto w-full">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Users className="w-7 h-7 text-[#2563eb]" />
            Clientes
          </h1>
          <p className="text-slate-600 mt-1 text-sm">
            Alta y listado de clientes para portes y facturación.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/clientes/onboarding"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <BarChart3 className="w-4 h-4" />
            Dashboard Onboarding
          </Link>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm mb-8">
        <h2 className="text-sm font-semibold text-slate-800 mb-3">Nuevo cliente</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-slate-600">Nombre / razón social</span>
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Ej. Transportes García SL"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">CIF / NIF (opcional)</span>
            <input
              value={nif}
              onChange={(e) => setNif(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="B12345678"
            />
          </label>
        </div>
        {formError && <p className="text-sm text-red-600 mt-2">{formError}</p>}
        <button
          type="button"
          onClick={() => void crear()}
          disabled={saving}
          className="mt-4 inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Guardando…
            </>
          ) : (
            "Registrar cliente"
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 mb-4">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
          <h2 className="text-sm font-semibold text-slate-800">Clientes activos</h2>
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-500 gap-2">
            <Loader2 className="w-5 h-5 animate-spin" />
            Cargando…
          </div>
        ) : rows.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-slate-500">
            Aún no hay clientes. Crea el primero arriba para usarlo en{" "}
            <Link href="/portes" className="text-[#2563eb] font-medium hover:underline">
              Portes
            </Link>
            .
          </p>
        ) : (
          <div className="w-full overflow-x-auto min-w-0">
            <table className="w-full min-w-[800px] text-sm text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80 text-slate-600">
                  <th className="px-5 py-3 font-semibold">Nombre / razón social</th>
                  <th className="hidden md:table-cell px-5 py-3 font-semibold w-[40%]">
                    ID (sistema)
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3 font-medium text-slate-900 align-top">
                      {r.nombre}
                    </td>
                    <td className="hidden md:table-cell px-5 py-3 text-xs text-slate-500 font-mono break-all align-top">
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
          <div className="p-8 max-w-lg">
            <p className="text-slate-700">Esta sección solo está disponible para el perfil de administrador.</p>
            <Link href="/dashboard" className="inline-block mt-4 text-[#2563eb] font-medium hover:underline">
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
