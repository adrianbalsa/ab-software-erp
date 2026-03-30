"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { RoleGuard } from "@/components/auth/RoleGuard";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import { CotizadorInteligente } from "@/components/portes/CotizadorInteligente";
import { AddressAutocomplete } from "@/components/maps/AddressAutocomplete";
import { GoogleMapsProvider, mapsApiKeyAvailable } from "@/components/maps/GoogleMapsProvider";
import { useRole } from "@/hooks/useRole";
import { API_BASE, jwtEmpresaId, notifyJwtUpdated } from "@/lib/api";

type PorteOut = {
  id: string;
  cliente_id?: string | null;
  fecha: string;
  origen: string;
  destino: string;
  km_estimados?: number;
  precio_pactado?: number | null;
  estado: string;
};

type ClienteRow = {
  id: string;
  nombre: string;
};

type FacturaGenerateResult = {
  factura: {
    id: string;
    numero_factura: string;
    num_factura?: string | null;
    total_factura: number;
    hash_registro?: string | null;
    hash_factura?: string | null;
  };
  portes_facturados: string[];
  pdf_base64?: string | null;
};

function formatClienteLabel(id: string) {
  if (id.length <= 12) return id;
  return `${id.slice(0, 8)}…${id.slice(-4)}`;
}

export default function PortesPage() {
  const { role } = useRole();
  const canCreatePorte = role === "owner" || role === "traffic_manager";
  const canFacturar = role === "owner";

  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [portes, setPortes] = useState<PorteOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facturarBusy, setFacturarBusy] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [successBanner, setSuccessBanner] = useState<{
    numFactura: string;
    hash: string;
  } | null>(null);

  const [clientes, setClientes] = useState<ClienteRow[]>([]);
  const [formKey, setFormKey] = useState(0);
  const [formCliente, setFormCliente] = useState("");
  const [formFecha, setFormFecha] = useState(() =>
    new Date().toISOString().slice(0, 10),
  );
  const [formOrigen, setFormOrigen] = useState("");
  const [formDestino, setFormDestino] = useState("");
  const [formKm, setFormKm] = useState("");
  const [formPrecio, setFormPrecio] = useState("");
  const [formBultos, setFormBultos] = useState("1");
  const [formBusy, setFormBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [creditToast, setCreditToast] = useState<ToastPayload | null>(null);

  const headerCheckboxRef = useRef<HTMLInputElement>(null);
  const mapsReady = mapsApiKeyAvailable();

  const authHeaders: Record<string, string> = token
    ? ({ Authorization: `Bearer ${token}` } as Record<string, string>)
    : {};

  const apiFetch = async (path: string, init?: RequestInit) => {
    const h = (init?.headers as Record<string, string> | undefined) || {};
    const needsJson =
      init?.body != null &&
      typeof init.body === "string" &&
      !h["Content-Type"] &&
      !h["content-type"];
    return fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...h,
        ...authHeaders,
        ...(needsJson ? { "Content-Type": "application/json" } : {}),
      },
    });
  };

  const login = async () => {
    setAuthError(null);
    setAuthBusy(true);
    try {
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Error en login");
      }
      const data = await res.json();
      setToken(data.access_token);
      try {
        localStorage.setItem("jwt_token", data.access_token);
        notifyJwtUpdated();
      } catch {
        // ignore
      }
    } catch (e: unknown) {
      setAuthError(e instanceof Error ? e.message : "Error");
    } finally {
      setAuthBusy(false);
    }
  };

  useEffect(() => {
    try {
      const saved = localStorage.getItem("jwt_token");
      if (saved) setToken(saved);
    } catch {
      // ignore
    }
  }, []);

  const loadPortes = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/portes/", { method: "GET" });
      if (!res.ok) throw new Error("No se pudieron cargar los portes");
      const data = (await res.json()) as PorteOut[];
      setPortes(data.filter((p) => p.estado === "pendiente"));
      setSelectedIds(new Set());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadClientes = useCallback(async () => {
    if (!token || !canCreatePorte) return;
    try {
      const res = await apiFetch("/clientes/", { method: "GET" });
      if (!res.ok) return;
      const rows = (await res.json()) as { id: string; nombre?: string | null }[];
      setClientes(
        rows.map((r) => ({
          id: r.id,
          nombre: (r.nombre || r.id).trim() || r.id,
        })),
      );
    } catch {
      setClientes([]);
    }
  }, [token, canCreatePorte]);

  useEffect(() => {
    void loadClientes();
  }, [loadClientes]);

  const crearPorte = async () => {
    if (!token || !formCliente.trim()) {
      setFormError("Selecciona un cliente.");
      return;
    }
    if (!formOrigen.trim() || !formDestino.trim()) {
      setFormError("Indica origen y destino.");
      return;
    }
    const precio = parseFloat(formPrecio.replace(",", "."));
    if (!Number.isFinite(precio) || precio <= 0) {
      setFormError("Indica un precio pactado válido.");
      return;
    }
    const bultos = Math.max(1, parseInt(formBultos, 10) || 1);
    const kmRaw = formKm.trim().replace(",", ".");
    const kmParsed = kmRaw === "" ? 0 : parseFloat(kmRaw);
    const km_estimados =
      Number.isFinite(kmParsed) && kmParsed > 0 ? kmParsed : 0;

    setFormBusy(true);
    setFormError(null);
    try {
      const res = await apiFetch("/portes/", {
        method: "POST",
        body: JSON.stringify({
          cliente_id: formCliente,
          fecha: formFecha,
          origen: formOrigen.trim(),
          destino: formDestino.trim(),
          km_estimados,
          bultos,
          precio_pactado: precio,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail =
          typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`;
        if (res.status === 403) {
          const friendly =
            detail.includes("Límite de crédito") || detail.includes("crédito")
              ? "El cliente está bloqueado por riesgo financiero: límite de crédito superado. Reduce el importe o cobra facturas pendientes."
              : detail;
          setCreditToast({
            id: Date.now(),
            message: friendly,
            tone: "error",
          });
          setFormError(friendly);
          return;
        }
        throw new Error(detail);
      }
      setFormOrigen("");
      setFormDestino("");
      setFormKm("");
      setFormPrecio("");
      setFormBultos("1");
      setFormKey((k) => k + 1);
      await loadPortes();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : "Error al crear porte");
    } finally {
      setFormBusy(false);
    }
  };

  useEffect(() => {
    loadPortes();
  }, [loadPortes]);

  const pendientes = useMemo(
    () => portes.filter((p) => p.estado === "pendiente"),
    [portes]
  );

  const selectedPortes = useMemo(
    () => pendientes.filter((p) => selectedIds.has(p.id)),
    [pendientes, selectedIds]
  );

  const totalSeleccionado = useMemo(
    () => selectedPortes.reduce((acc, p) => acc + Number(p.precio_pactado ?? 0), 0),
    [selectedPortes]
  );

  const clientesEnSeleccion = useMemo(() => {
    const s = new Set(
      selectedPortes.map((p) => p.cliente_id).filter((id): id is string => Boolean(id)),
    );
    return s.size;
  }, [selectedPortes]);

  const allSelected =
    pendientes.length > 0 && selectedIds.size === pendientes.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  useEffect(() => {
    const el = headerCheckboxRef.current;
    if (el) el.indeterminate = someSelected;
  }, [someSelected, allSelected]);

  const toggleRow = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) setSelectedIds(new Set());
    else setSelectedIds(new Set(pendientes.map((p) => p.id)));
  };

  const facturarSeleccionados = async () => {
    if (!token || selectedPortes.length === 0) return;
    if (clientesEnSeleccion > 1) {
      alert(
        "Selecciona solo portes del mismo cliente. La factura legal es por cliente."
      );
      return;
    }
    const clienteId = selectedPortes[0].cliente_id;
    if (!clienteId) {
      alert("No hay cliente asociado a la selección.");
      return;
    }
    const porte_ids = selectedPortes.map((p) => p.id);

    setFacturarBusy(true);
    setSuccessBanner(null);
    try {
      const res = await apiFetch("/facturas/desde-portes", {
        method: "POST",
        body: JSON.stringify({
          cliente_id: clienteId,
          iva_porcentaje: 21,
          porte_ids,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err?.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail.map((d: { msg?: string }) => d.msg).join(", ")
              : `HTTP ${res.status}`
        );
      }
      const json = (await res.json()) as FacturaGenerateResult;
      const numFactura =
        json.factura.num_factura?.trim() ||
        json.factura.numero_factura ||
        "—";
      const hash =
        json.factura.hash_registro?.trim() ||
        json.factura.hash_factura?.trim() ||
        "—";

      setSuccessBanner({ numFactura, hash });

      if (json.pdf_base64) {
        const blob = new Blob(
          [Uint8Array.from(atob(json.pdf_base64), (c) => c.charCodeAt(0))],
          { type: "application/pdf" }
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${numFactura.replace(/[^\w.-]+/g, "_")}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }

      setSelectedIds(new Set());
      await loadPortes();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al facturar");
    } finally {
      setFacturarBusy(false);
    }
  };

  const selectionOpen = canFacturar && selectedIds.size > 0;

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-white border rounded-2xl p-6 space-y-4 shadow-sm">
          <h1 className="text-xl font-bold text-slate-800">Portes — Login</h1>
          <input
            className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
            placeholder="Usuario"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="w-full border border-slate-200 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 outline-none"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {authError && <p className="text-sm text-red-600">{authError}</p>}
          <button
            onClick={login}
            disabled={authBusy}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg font-medium disabled:opacity-50 transition-colors"
          >
            {authBusy ? "…" : "Entrar"}
          </button>
          <Link href="/dashboard" className="block text-center text-sm text-blue-600 hover:underline">
            Volver al dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`min-h-screen ab-app-gradient ${selectionOpen ? "pb-28 sm:pb-10" : "pb-10"}`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Portes pendientes
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Selecciona filas y factura con encadenamiento VeriFactu.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => loadPortes()}
              disabled={loading}
              className="text-sm px-3 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {loading ? "Actualizando…" : "Actualizar"}
            </button>
            <Link
              href="/dashboard"
              className="text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              Dashboard
            </Link>
          </div>
        </div>

        {successBanner && (
          <div
            role="status"
            className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50/90 p-4 shadow-sm"
          >
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div className="space-y-2">
                <p className="text-sm font-semibold text-emerald-900">
                  Factura emitida correctamente
                </p>
                <dl className="grid gap-1 text-sm">
                  <div className="flex flex-wrap gap-x-2">
                    <dt className="text-emerald-700/90">Nº factura</dt>
                    <dd className="font-mono font-medium text-emerald-950">
                      {successBanner.numFactura}
                    </dd>
                  </div>
                  <div className="flex flex-col gap-1">
                    <dt className="text-emerald-700/90">Hash VeriFactu</dt>
                    <dd className="font-mono text-xs break-all text-emerald-950 bg-white/60 rounded-lg px-2 py-1.5 border border-emerald-100">
                      {successBanner.hash}
                    </dd>
                  </div>
                </dl>
              </div>
              <button
                type="button"
                onClick={() => setSuccessBanner(null)}
                className="shrink-0 text-sm text-emerald-800 hover:underline self-start"
              >
                Cerrar
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-3">
            {error}
          </div>
        )}

        {token ? (
          <RoleGuard allowedRoles={["owner", "traffic_manager"]}>
            {jwtEmpresaId() ? (
              <div className="mb-8">
                <CotizadorInteligente empresaId={jwtEmpresaId()!} />
              </div>
            ) : null}
          </RoleGuard>
        ) : null}

        {canCreatePorte ? (
        <div className="mb-8 ab-card rounded-2xl p-6">
          <h2 className="text-lg font-bold text-slate-900">Nuevo porte</h2>
          <p className="text-sm text-slate-500 mt-1">
            Origen y destino en texto; si dejas los km en blanco, el backend calcula la
            distancia con Google Distance Matrix (clave{" "}
            <code className="text-xs bg-slate-100 px-1 rounded">MAPS_API_KEY</code>).
          </p>
          {formError && (
            <p
              role="alert"
              className={`mt-3 text-sm rounded-lg px-3 py-2 border ${
                formError.includes("riesgo financiero") || formError.includes("crédito")
                  ? "text-red-900 bg-red-100 border-red-400 font-medium"
                  : "text-red-700 bg-red-50 border-red-200"
              }`}
            >
              {formError}
            </p>
          )}
          <GoogleMapsProvider>
            <div
              key={formKey}
              className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            >
              <label className="block sm:col-span-2 lg:col-span-1">
                <span className="text-sm font-medium text-slate-700">Cliente</span>
                <select
                  value={formCliente}
                  onChange={(e) => setFormCliente(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm"
                >
                  <option value="">— Seleccionar —</option>
                  {clientes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Fecha</span>
                <input
                  type="date"
                  value={formFecha}
                  onChange={(e) => setFormFecha(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Km (opcional)</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formKm}
                  onChange={(e) => setFormKm(e.target.value)}
                  placeholder="Auto si vacío"
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-mono"
                />
              </label>
              {mapsReady ? (
                <>
                  <AddressAutocomplete
                    id={`origen-${formKey}`}
                    label="Origen"
                    defaultValue=""
                    onChange={setFormOrigen}
                    placeholder="Calle, ciudad…"
                  />
                  <AddressAutocomplete
                    id={`destino-${formKey}`}
                    label="Destino"
                    defaultValue=""
                    onChange={setFormDestino}
                    placeholder="Calle, ciudad…"
                  />
                </>
              ) : (
                <>
                  <label className="block sm:col-span-2">
                    <span className="text-sm font-medium text-slate-700">Origen</span>
                    <input
                      value={formOrigen}
                      onChange={(e) => setFormOrigen(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
                      placeholder="Dirección completa"
                    />
                  </label>
                  <label className="block sm:col-span-2">
                    <span className="text-sm font-medium text-slate-700">Destino</span>
                    <input
                      value={formDestino}
                      onChange={(e) => setFormDestino(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
                      placeholder="Dirección completa"
                    />
                  </label>
                  <p className="sm:col-span-2 lg:col-span-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    Sin <code className="font-mono">NEXT_PUBLIC_MAPS_API_KEY</code> no hay
                    autocompletado; puedes escribir direcciones a mano.
                  </p>
                </>
              )}
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Precio (€)</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={formPrecio}
                  onChange={(e) => setFormPrecio(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-mono"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Bultos</span>
                <input
                  type="number"
                  min={1}
                  value={formBultos}
                  onChange={(e) => setFormBultos(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
                />
              </label>
              <div className="flex items-end sm:col-span-2 lg:col-span-1">
                <button
                  type="button"
                  onClick={() => void crearPorte()}
                  disabled={formBusy}
                  className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
                >
                  {formBusy ? "Guardando…" : "Crear porte"}
                </button>
              </div>
            </div>
          </GoogleMapsProvider>
        </div>
        ) : null}

        {clientesEnSeleccion > 1 && selectionOpen && (
          <div className="mb-4 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3">
            Has mezclado portes de <strong>varios clientes</strong>. La facturación
            debe ser por un solo cliente; ajusta la selección.
          </div>
        )}

        {/* Barra superior compacta cuando hay selección (desktop) */}
        {selectionOpen && (
          <div className="hidden sm:flex mb-4 items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-sm text-slate-600">
              <span className="font-semibold text-slate-900">{selectedIds.size}</span>{" "}
              seleccionado(s) · Total{" "}
              <span className="font-mono font-semibold text-slate-900">
                {totalSeleccionado.toFixed(2)} €
              </span>
            </p>
            <button
              type="button"
              onClick={facturarSeleccionados}
              disabled={
                facturarBusy ||
                clientesEnSeleccion > 1 ||
                selectedPortes.length === 0
              }
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:pointer-events-none transition-colors"
            >
              {facturarBusy ? (
                "Facturando…"
              ) : (
                <>
                  Facturar seleccionados ({selectedIds.size})
                  <span className="opacity-90">· {totalSeleccionado.toFixed(2)} €</span>
                </>
              )}
            </button>
          </div>
        )}

        {loading ? (
          <div className="ab-card rounded-2xl p-12 text-center text-slate-500">
            Cargando portes…
          </div>
        ) : (
          <div className="ab-card overflow-hidden rounded-2xl p-0">
            <div className="w-full overflow-x-auto min-w-0">
              <table className="ab-table w-full min-w-[800px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/90 text-slate-600">
                    {canFacturar ? (
                    <th className="w-12 px-3 py-3">
                      <input
                        ref={headerCheckboxRef}
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        aria-label="Seleccionar todos los portes pendientes"
                      />
                    </th>
                    ) : null}
                    <th className="hidden md:table-cell px-3 py-3 font-semibold whitespace-nowrap">
                      Fecha
                    </th>
                    <th className="hidden md:table-cell px-3 py-3 font-semibold">Cliente</th>
                    <th className="px-3 py-3 font-semibold">Origen</th>
                    <th className="px-3 py-3 font-semibold">Destino</th>
                    <th className="px-3 py-3 font-semibold whitespace-nowrap">Estado</th>
                    <th className="hidden md:table-cell px-3 py-3 font-semibold text-right whitespace-nowrap">
                      Precio pactado
                    </th>
                    <th className="hidden md:table-cell px-3 py-3 font-semibold whitespace-nowrap w-24">
                      Detalle
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pendientes.map((p) => {
                    const checked = selectedIds.has(p.id);
                    return (
                      <tr
                        key={p.id}
                        className={`transition-colors hover:bg-slate-50/80 ${checked ? "bg-blue-50/40" : ""}`}
                      >
                        {canFacturar ? (
                        <td className="px-3 py-3 align-middle">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleRow(p.id)}
                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            aria-label={`Seleccionar porte ${p.id}`}
                          />
                        </td>
                        ) : null}
                        <td className="hidden md:table-cell px-3 py-3 align-middle whitespace-nowrap text-slate-800">
                          {p.fecha}
                        </td>
                        <td className="hidden md:table-cell px-3 py-3 align-middle">
                          <span
                            className="font-mono text-xs text-slate-700"
                            title={p.cliente_id ?? undefined}
                          >
                            {p.cliente_id ? formatClienteLabel(p.cliente_id) : "—"}
                          </span>
                        </td>
                        <td className="px-3 py-3 align-middle text-slate-800 max-w-[200px] md:max-w-none">
                          <span className="line-clamp-2 md:line-clamp-none">{p.origen}</span>
                        </td>
                        <td className="px-3 py-3 align-middle text-slate-800 max-w-[200px] md:max-w-none">
                          <span className="line-clamp-2 md:line-clamp-none">{p.destino}</span>
                        </td>
                        <td className="px-3 py-3 align-middle">
                          <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-700">
                            {p.estado}
                          </span>
                        </td>
                        <td className="hidden md:table-cell px-3 py-3 align-middle text-right font-mono tabular-nums text-slate-900">
                          {p.precio_pactado != null
                            ? `${Number(p.precio_pactado).toFixed(2)} €`
                            : "—"}
                        </td>
                        <td className="hidden md:table-cell px-3 py-3 align-middle">
                          <Link
                            href={`/portes/${p.id}`}
                            className="text-sm font-medium text-blue-600 hover:underline"
                          >
                            Ver ruta
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {pendientes.length === 0 && (
              <p className="py-12 text-center text-slate-500 text-sm">
                No hay portes en estado pendiente.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Acción masiva: barra flotante inferior (móvil + refuerzo visual) */}
      <ToastHost
        toast={creditToast}
        onDismiss={() => setCreditToast(null)}
        durationMs={7200}
      />

      {selectionOpen && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur-md shadow-[0_-8px_30px_rgba(15,23,42,0.12)] sm:hidden">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide">
                Total seleccionado
              </p>
              <p className="text-lg font-bold text-slate-900 tabular-nums">
                {totalSeleccionado.toFixed(2)} €
              </p>
            </div>
            <button
              type="button"
              onClick={facturarSeleccionados}
              disabled={
                facturarBusy ||
                clientesEnSeleccion > 1 ||
                selectedPortes.length === 0
              }
              className="flex-1 max-w-[min(100%,14rem)] rounded-full bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700 disabled:opacity-50 disabled:shadow-none transition-all"
            >
              {facturarBusy
                ? "Facturando…"
                : `Facturar (${selectedIds.size})`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
