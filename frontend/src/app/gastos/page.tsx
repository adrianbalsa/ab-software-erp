"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CreditCard,
  LayoutDashboard,
  Package,
  Receipt,
  Settings,
  Truck,
} from "lucide-react";
import { API_BASE, authHeaders, notifyJwtUpdated } from "@/lib/api";
import { clearAuthToken, getAuthToken, setAuthToken } from "@/lib/auth";

/** Respuesta de POST /gastos/ocr-hint (sin confirmar). */
type GastoOCRHint = {
  proveedor?: string | null;
  fecha?: string | null;
  total?: number | null;
  moneda?: string | null;
  concepto?: string | null;
  nif_proveedor?: string | null;
  iva?: number | null;
};

type GastoOut = {
  id: string;
  evidencia_url?: string | null;
  proveedor: string;
  total_eur?: number | null;
};

const CATEGORIAS = [
  "Materiales",
  "Combustible",
  "Dietas",
  "Hospedaje",
  "Suministros",
  "Varios",
] as const;

/** Normaliza fecha ISO (con o sin hora) a YYYY-MM-DD para `<input type="date">`. */
function formatDateForInput(d: string | Date | null | undefined): string {
  if (!d) return "";
  if (typeof d === "string") {
    const s = d.trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const t = Date.parse(s);
    if (!Number.isNaN(t)) return new Date(t).toISOString().slice(0, 10);
    return "";
  }
  if (d instanceof Date && !Number.isNaN(d.getTime())) {
    return d.toISOString().slice(0, 10);
  }
  return "";
}

function formatAmountForInput(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

export default function GastosPage() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [proveedor, setProveedor] = useState("");
  const [fecha, setFecha] = useState("");
  const [totalChf, setTotalChf] = useState("");
  const [totalEur, setTotalEur] = useState("");
  const [moneda, setMoneda] = useState("EUR");
  const [categoria, setCategoria] = useState<string>(CATEGORIAS[0]);
  const [concepto, setConcepto] = useState("");
  const [nifProveedor, setNifProveedor] = useState("");
  const [iva, setIva] = useState("");

  useEffect(() => {
    try {
      const t = getAuthToken();
      if (t) setToken(t);
    } catch {
      // ignore
    }
  }, []);

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
      setAuthToken(data.access_token);
      notifyJwtUpdated();
    } catch (e: unknown) {
      setAuthError(e instanceof Error ? e.message : "Error");
    } finally {
      setAuthBusy(false);
    }
  };

  const logout = () => {
    setToken(null);
    try {
      clearAuthToken();
    } catch {
      // ignore
    }
  };

  const applyHints = useCallback((h: GastoOCRHint) => {
    if (h.proveedor != null && String(h.proveedor).trim() !== "") {
      setProveedor(String(h.proveedor).trim());
    }
    const fechaNorm = formatDateForInput(
      typeof h.fecha === "string" ? h.fecha : h.fecha != null ? String(h.fecha) : "",
    );
    if (fechaNorm) {
      setFecha(fechaNorm);
    } else if (
      (h.total != null && h.total > 0) ||
      (h.proveedor != null && String(h.proveedor).trim() !== "")
    ) {
      setFecha(formatDateForInput(new Date().toISOString()));
    }
    if (h.moneda != null && String(h.moneda).trim() !== "") {
      setMoneda(String(h.moneda).toUpperCase().slice(0, 3));
    }
    if (h.concepto != null && String(h.concepto).trim() !== "") {
      setConcepto(String(h.concepto).trim());
    }
    if (h.nif_proveedor != null && String(h.nif_proveedor).trim() !== "") {
      setNifProveedor(String(h.nif_proveedor).trim().toUpperCase());
    }
    if (h.iva != null && typeof h.iva === "number" && !Number.isNaN(h.iva)) {
      setIva(formatAmountForInput(h.iva));
    }
    if (h.total != null && typeof h.total === "number" && !Number.isNaN(h.total) && h.total > 0) {
      const amt = formatAmountForInput(h.total);
      setTotalChf(amt);
      const m = (h.moneda || "EUR").toUpperCase();
      if (m === "EUR") setTotalEur(amt);
      else setTotalEur("");
    }
  }, []);

  /** POST /gastos/ocr-hint sin confirmar → hints para rellenar el formulario. */
  const runOcrHint = async () => {
    setError(null);
    setSuccess(null);
    if (!file) {
      setError("Selecciona un archivo (ticket o factura).");
      return;
    }
    setOcrBusy(true);
    try {
      const fd = new FormData();
      fd.append("confirm", "false");
      fd.append("evidencia", file);

      const res = await fetch(`${API_BASE}/gastos/ocr-hint`, {
        method: "POST",
        credentials: "include",
        headers: { ...authHeaders() },
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const hint = (await res.json()) as GastoOCRHint;
      applyHints(hint);
      setSuccess(
        "Datos sugeridos cargados. Revisa el formulario y confirma el registro.",
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error OCR");
    } finally {
      setOcrBusy(false);
    }
  };

  /** POST /gastos/ocr-hint con confirm=true → persiste gasto y sube evidencia al bucket tickets. */
  const confirmarGasto = async () => {
    setError(null);
    setSuccess(null);
    if (!file) {
      setError("Se requiere el archivo de evidencia para guardar en el bucket.");
      return;
    }
    const tc = parseFloat(totalChf.replace(",", "."));
    if (!proveedor.trim() || !fecha.trim() || Number.isNaN(tc) || tc <= 0) {
      setError("Completa proveedor, fecha e importe total válido.");
      return;
    }

    setConfirmBusy(true);
    try {
      const fd = new FormData();
      fd.append("confirm", "true");
      fd.append("proveedor", proveedor.trim());
      fd.append("fecha", fecha.trim());
      fd.append("total_chf", String(tc));
      fd.append("categoria", categoria);
      fd.append("moneda", moneda || "EUR");
      if (concepto.trim()) fd.append("concepto", concepto.trim());
      if (nifProveedor.trim()) fd.append("nif_proveedor", nifProveedor.trim());
      if (iva.trim()) fd.append("iva", iva.replace(",", "."));
      const te = totalEur.trim()
        ? parseFloat(totalEur.replace(",", "."))
        : null;
      if (te != null && !Number.isNaN(te) && te > 0) {
        fd.append("total_eur", String(te));
      }
      fd.append("evidencia", file);

      const res = await fetch(`${API_BASE}/gastos/ocr-hint`, {
        method: "POST",
        credentials: "include",
        headers: { ...authHeaders() },
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }
      const created = (await res.json()) as GastoOut;
      setSuccess(
        `Gasto registrado. Evidencia: ${created.evidencia_url ?? "subida al bucket tickets"}.`,
      );
      setFile(null);
      setProveedor("");
      setFecha("");
      setTotalChf("");
      setTotalEur("");
      setConcepto("");
      setNifProveedor("");
      setIva("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al guardar");
    } finally {
      setConfirmBusy(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
          <h1 className="text-xl font-bold text-slate-800 mb-2">Gastos</h1>
          <p className="text-sm text-slate-600 mb-6">
            Inicia sesión para subir tickets y digitalizar gastos.
          </p>
          {authError && (
            <div className="mb-4 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {authError}
            </div>
          )}
          <input
            className="w-full border rounded-lg px-3 py-2 mb-2 text-slate-800"
            placeholder="Usuario"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            className="w-full border rounded-lg px-3 py-2 mb-4 text-slate-800"
            type="password"
            placeholder="Contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={() => void login()}
            disabled={authBusy}
            className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
          >
            {authBusy ? "Entrando…" : "Entrar"}
          </button>
          <Link
            href="/dashboard"
            className="block text-center text-sm text-blue-600 mt-4 hover:underline"
          >
            Volver al dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans">
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <Truck className="w-6 h-6 text-blue-400 mr-2" />
          <span className="text-white font-bold text-lg">AB Logistics OS</span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          <Link
            href="/dashboard"
            className="flex items-center px-3 py-2.5 hover:bg-slate-800 rounded-lg"
          >
            <LayoutDashboard className="w-5 h-5 mr-3" />
            Dashboard
          </Link>
          <Link
            href="/portes"
            className="flex items-center px-3 py-2.5 hover:bg-slate-800 rounded-lg"
          >
            <Truck className="w-5 h-5 mr-3" />
            Portes
          </Link>
          <Link
            href="/gastos"
            className="flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg"
          >
            <CreditCard className="w-5 h-5 mr-3" />
            Gastos
          </Link>
          <Link
            href="/sostenibilidad"
            className="flex items-center px-3 py-2.5 hover:bg-slate-800 rounded-lg"
          >
            <Package className="w-5 h-5 mr-3" />
            Sostenibilidad
          </Link>
          <span className="flex items-center px-3 py-2.5 opacity-50 cursor-not-allowed">
            <Receipt className="w-5 h-5 mr-3" />
            Facturas
          </span>
          <span className="flex items-center px-3 py-2.5 opacity-50 cursor-not-allowed">
            <Settings className="w-5 h-5 mr-3" />
            Admin
          </span>
        </nav>
        <div className="p-4 border-t border-slate-800">
          <button
            type="button"
            onClick={logout}
            className="text-sm text-slate-400 hover:text-white"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">
          Digitalización de gastos
        </h1>
        <p className="text-slate-600 text-sm mb-8">
          Sube un ticket: el backend devuelve sugerencias OCR; revisa los datos y
          confirma para guardar en Supabase y la evidencia en el bucket{" "}
          <code className="bg-slate-100 px-1 rounded">tickets</code>.
        </p>

        {error && (
          <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-100 px-4 py-3 rounded-xl">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 text-sm text-emerald-800 bg-emerald-50 border border-emerald-100 px-4 py-3 rounded-xl">
            {success}
          </div>
        )}

        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm mb-6">
          <h2 className="font-semibold text-slate-800 mb-4">1. Evidencia</h2>
          <input
            type="file"
            accept="image/*,.pdf,application/pdf"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setSuccess(null);
            }}
            className="block w-full text-sm text-slate-600"
          />
          <button
            type="button"
            onClick={() => void runOcrHint()}
            disabled={ocrBusy || !file}
            className="mt-4 px-4 py-2.5 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {ocrBusy ? "Solicitando sugerencias…" : "Extraer datos (OCR hint)"}
          </button>
          <p className="mt-2 text-xs text-slate-500">
            Llama a <code className="bg-slate-100 px-1">POST /gastos/ocr-hint</code>{" "}
            con <code className="bg-slate-100 px-1">confirm=false</code>.
          </p>
        </section>

        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h2 className="font-semibold text-slate-800 mb-2">
            2. Datos del gasto (VeriFactu-ready)
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-slate-500">
                Proveedor
              </span>
              <input
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                value={proveedor}
                onChange={(e) => setProveedor(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">Fecha</span>
              <input
                type="date"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">
                Importe total (ticket)
              </span>
              <input
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                inputMode="decimal"
                value={totalChf}
                onChange={(e) => setTotalChf(e.target.value)}
                placeholder="0.00"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">Moneda</span>
              <select
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                value={moneda}
                onChange={(e) => setMoneda(e.target.value)}
              >
                <option value="EUR">EUR</option>
                <option value="CHF">CHF</option>
                <option value="USD">USD</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">
                Total EUR (opcional)
              </span>
              <input
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                inputMode="decimal"
                value={totalEur}
                onChange={(e) => setTotalEur(e.target.value)}
                placeholder="Mismo que importe si EUR"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">
                NIF proveedor
              </span>
              <input
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                value={nifProveedor}
                onChange={(e) => setNifProveedor(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500">
                IVA (EUR)
              </span>
              <input
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                inputMode="decimal"
                value={iva}
                onChange={(e) => setIva(e.target.value)}
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="text-xs font-medium text-slate-500">
                Categoría
              </span>
              <select
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
              >
                {CATEGORIAS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="text-xs font-medium text-slate-500">
                Concepto
              </span>
              <textarea
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-slate-800 min-h-[80px]"
                value={concepto}
                onChange={(e) => setConcepto(e.target.value)}
              />
            </label>
          </div>

          <button
            type="button"
            onClick={() => void confirmarGasto()}
            disabled={confirmBusy || !file}
            className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold disabled:opacity-50"
          >
            {confirmBusy ? "Guardando…" : "Confirmar y registrar gasto"}
          </button>
          <p className="text-xs text-slate-500">
            <code className="bg-slate-100 px-1">POST /gastos/ocr-hint</code> con{" "}
            <code className="bg-slate-100 px-1">confirm=true</code>: persiste fila
            en <code className="bg-slate-100 px-1">gastos</code> y sube el archivo a
            Storage (<code className="bg-slate-100 px-1">tickets</code>).
          </p>
        </section>
      </main>
    </div>
  );
}
