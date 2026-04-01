"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_BASE, apiFetch } from "@/lib/api";
import { getAuthToken } from "@/lib/auth";
import {
  clearPresupuestoDraft,
  loadPresupuestoDraft,
  savePresupuestoDraft,
  type PresupuestoDraft,
} from "@/lib/presupuestoDraft";
import { ToastHost, type ToastPayload } from "@/components/ui/ToastHost";
import {
  Calculator,
  HardHat,
  Users,
  Package,
  Save,
  FileText,
  Plus,
  Trash2,
  Building2,
  Briefcase,
  X,
} from "lucide-react";

/** Cuerpo JSON alineado con `PresupuestoCalculoIn` (backend). */
type PresupuestoCalculoInBody = {
  metros_obra: number;
  precio_m2: number;
  num_trabajadores: number;
  horas_por_trab: number;
  coste_hora: number;
  materiales: { descripcion: string | null; cantidad: number; precio: number }[];
  margen_pct: number;
  iva_pct: number;
  moneda: string | null;
  verifactu?: {
    nif_empresa: string;
    nif_cliente: string;
    num_documento: string;
    fecha: string;
    hash_anterior?: string | null;
  };
};

function readJwtPresent(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const t = getAuthToken();
    return typeof t === "string" && t.length > 0;
  } catch {
    return false;
  }
}

export default function PresupuestosPage() {
  const router = useRouter();

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showLoginWall, setShowLoginWall] = useState(false);
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const draftRestored = useRef(false);

  // --- ESTADOS DEL FORMULARIO ---
  const [cliente, setCliente] = useState("");
  const [nif, setNif] = useState("");
  const [divisa, setDivisa] = useState("EUR");

  const [metros, setMetros] = useState(0);
  const [precioM2, setPrecioM2] = useState(0);

  const [trabajadores, setTrabajadores] = useState(0);
  const [horas, setHoras] = useState(0);
  const [costeHora, setCosteHora] = useState(0);

  const [materiales, setMateriales] = useState([{ desc: "", cant: 1, precio: 0 }]);

  const [margen, setMargen] = useState(15);
  const [iva, setIva] = useState(21);

  const pushToast = useCallback((message: string, tone: ToastPayload["tone"]) => {
    setToast({ id: Date.now(), message, tone });
  }, []);

  const collectDraft = useCallback((): PresupuestoDraft => {
    return {
      cliente,
      nif,
      divisa,
      metros,
      precioM2,
      trabajadores,
      horas,
      costeHora,
      materiales: materiales.map((m) => ({ ...m })),
      margen,
      iva,
    };
  }, [
    cliente,
    nif,
    divisa,
    metros,
    precioM2,
    trabajadores,
    horas,
    costeHora,
    materiales,
    margen,
    iva,
  ]);

  // JWT en localStorage solo en cliente; tras hidratar sincronizamos sesión.
  /* eslint-disable react-hooks/set-state-in-effect -- lectura localStorage/sessionStorage tras mount */
  useEffect(() => {
    setIsLoggedIn(readJwtPresent());
  }, []);

  useEffect(() => {
    if (draftRestored.current) return;
    const d = loadPresupuestoDraft();
    if (!d) return;
    draftRestored.current = true;
    setCliente(d.cliente ?? "");
    setNif(d.nif ?? "");
    setDivisa(d.divisa || "EUR");
    setMetros(Number(d.metros) || 0);
    setPrecioM2(Number(d.precioM2) || 0);
    setTrabajadores(Number(d.trabajadores) || 0);
    setHoras(Number(d.horas) || 0);
    setCosteHora(Number(d.costeHora) || 0);
    if (Array.isArray(d.materiales) && d.materiales.length > 0) {
      setMateriales(
        d.materiales.map((m) => ({
          desc: m.desc ?? "",
          cant: Number(m.cant) || 0,
          precio: Number(m.precio) || 0,
        })),
      );
    }
    setMargen(Number(d.margen) || 15);
    setIva(Number(d.iva) || 21);
    pushToast("Hemos recuperado tu borrador de presupuesto.", "info");
  }, [pushToast]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const subtotalObra = metros * precioM2;
  const subtotalMo = trabajadores * horas * costeHora;
  const subtotalMateriales = materiales.reduce((acc, curr) => acc + curr.cant * curr.precio, 0);

  const subtotalBase = subtotalObra + subtotalMo + subtotalMateriales;
  const subtotalConMargen = subtotalBase * (1 + margen / 100);
  const cuotaIva = subtotalConMargen * (iva / 100);
  const totalFinal = subtotalConMargen + cuotaIva;

  const addMaterial = () => setMateriales([...materiales, { desc: "", cant: 1, precio: 0 }]);
  const removeMaterial = (index: number) => setMateriales(materiales.filter((_, i) => i !== index));
  const updateMaterial = (index: number, field: string, value: string | number) => {
    const newMats = [...materiales];
    newMats[index] = { ...newMats[index], [field]: value };
    setMateriales(newMats);
  };

  const descargarCertificado = async () => {
    try {
      const payload = {
        distancia_km: metros / 10,
        toneladas_carga: 24,
        tipo_combustible: "hibrido",
      };

      const response = await apiFetch(`${API_BASE}/eco/certificado-pdf`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 401) {
        setIsLoggedIn(false);
        pushToast(
          "Tu sesión ha caducado. Inicia sesión de nuevo para descargar el certificado.",
          "error",
        );
        return;
      }

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "Certificado_ESG_ABLogistics.pdf";
        a.click();
        pushToast("Certificado descargado correctamente.", "success");
      } else {
        pushToast("No se pudo generar el PDF. Inténtalo de nuevo en unos minutos.", "error");
      }
    } catch {
      pushToast("Sin conexión con el servidor. Comprueba tu red e inténtalo de nuevo.", "error");
    }
  };

  const registrarPresupuesto = async () => {
    if (!readJwtPresent()) {
      setIsLoggedIn(false);
      setShowLoginWall(true);
      return;
    }

    try {
      const payload: PresupuestoCalculoInBody = {
        metros_obra: metros,
        precio_m2: precioM2,
        num_trabajadores: Math.max(0, Math.floor(trabajadores)),
        horas_por_trab: horas,
        coste_hora: costeHora,
        materiales: materiales.map((m) => ({
          descripcion: m.desc?.trim() ? m.desc.trim() : null,
          cantidad: m.cant,
          precio: m.precio,
        })),
        margen_pct: margen,
        iva_pct: iva,
        moneda: divisa || "EUR",
        verifactu: {
          nif_empresa: "B12345678",
          nif_cliente: (nif || "B00000000").trim(),
          num_documento: "PRE-2026-0001",
          fecha: new Date().toISOString().split("T")[0],
        },
      };

      const response = await apiFetch(`${API_BASE}/presupuestos/calcular`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 401) {
        setIsLoggedIn(false);
        pushToast(
          "Necesitas iniciar sesión para registrar el presupuesto y mantener la trazabilidad.",
          "error",
        );
        setShowLoginWall(true);
        return;
      }

      if (response.ok) {
        const data = await response.json();
        setIsLoggedIn(true);
        clearPresupuestoDraft();
        pushToast(
          `Presupuesto registrado. Total: ${data.total_final} ${divisa}. Hash: ${data.hash_documento ?? "—"}`,
          "success",
        );
      } else {
        let detail = "No se pudo registrar el presupuesto.";
        try {
          const errBody = await response.json();
          if (typeof errBody?.detail === "string") detail = errBody.detail;
        } catch {
          /* ignore */
        }
        pushToast(detail, "error");
      }
    } catch {
      pushToast("No pudimos conectar con el servidor. Revisa la conexión e inténtalo otra vez.", "error");
    }
  };

  const handleIrALogin = () => {
    savePresupuestoDraft(collectDraft());
    setShowLoginWall(false);
    router.push(`/login?redirect=${encodeURIComponent("/presupuestos")}`);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans flex flex-col md:flex-row">
      <ToastHost toast={toast} onDismiss={() => setToast(null)} />

      {showLoginWall && (
        <div
          className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="login-wall-title"
        >
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-2xl">
            <button
              type="button"
              onClick={() => setShowLoginWall(false)}
              className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              aria-label="Cerrar"
            >
              <X className="h-5 w-5" />
            </button>
            <h2
              id="login-wall-title"
              className="text-xl font-bold tracking-tight text-slate-900 pr-8"
            >
              Guarda tu Presupuesto
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-600">
              Para registrar este cálculo y mantener la trazabilidad de tus márgenes, necesitas
              iniciar sesión o crear una cuenta en tu empresa.
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Tus datos del formulario se guardan en esta sesión y se restauran al volver.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row-reverse">
              <button
                type="button"
                onClick={handleIrALogin}
                className="flex-1 rounded-xl bg-blue-600 py-3 text-center font-bold text-white shadow-lg shadow-blue-900/20 transition-colors hover:bg-blue-500"
              >
                Iniciar Sesión
              </button>
              <button
                type="button"
                onClick={() => setShowLoginWall(false)}
                className="flex-1 rounded-xl border border-slate-300 bg-white py-3 font-semibold text-slate-700 transition-colors hover:bg-slate-50"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      <aside className="w-64 bg-slate-900 text-slate-300 hidden md:flex flex-col min-h-screen">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <Building2 className="w-6 h-6 text-blue-400 mr-2" />
          <span className="text-white font-bold text-lg tracking-tight">AB Logistics OS</span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          <Link
            href="/dashboard"
            className="flex items-center px-3 py-2.5 hover:bg-slate-800 hover:text-white rounded-lg transition-colors"
          >
            <span className="font-medium">Dashboard</span>
          </Link>
          <Link
            href="/presupuestos"
            className="flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg"
          >
            <Calculator className="w-5 h-5 mr-3" />
            <span className="font-medium">Presupuestos</span>
          </Link>
          {!isLoggedIn && (
            <Link
              href="/login?redirect=%2Fpresupuestos"
              className="mt-4 flex items-center px-3 py-2.5 text-sm text-slate-400 hover:text-white rounded-lg border border-slate-700 hover:border-slate-600"
            >
              Iniciar sesión
            </Link>
          )}
        </nav>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 z-10 sticky top-0">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight flex items-center">
            <FileText className="mr-3 text-blue-600" /> Editor de Presupuestos
          </h1>
          <span
            className={`text-xs font-semibold uppercase tracking-wide ${isLoggedIn ? "text-emerald-600" : "text-amber-600"}`}
          >
            {isLoggedIn ? "Sesión activa" : "Sin sesión — registro requiere login"}
          </span>
        </header>

        <div className="p-8 max-w-7xl mx-auto space-y-6">
          <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
              <Briefcase className="w-5 h-5 mr-2 text-slate-500" /> Datos del Proyecto
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="col-span-1 md:col-span-2">
                <label className="block text-sm font-medium text-slate-600 mb-1">
                  Cliente / Razón Social
                </label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Ej: Tech Solutions SL"
                  value={cliente}
                  onChange={(e) => setCliente(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">NIF/CIF Cliente</label>
                <input
                  type="text"
                  className="w-full p-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="B12345678"
                  value={nif}
                  onChange={(e) => setNif(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 mb-1">Divisa</label>
                <select
                  className="w-full p-2.5 border border-slate-300 rounded-lg outline-none bg-white"
                  value={divisa}
                  onChange={(e) => setDivisa(e.target.value)}
                >
                  <option>EUR</option>
                  <option>CHF</option>
                  <option>USD</option>
                </select>
              </div>
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                  <HardHat className="w-5 h-5 mr-2 text-amber-500" /> Ingeniería y Obra Civil
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">Cantidad (m²)</label>
                    <input
                      type="number"
                      min="0"
                      className="w-full p-2.5 border border-slate-300 rounded-lg"
                      value={metros}
                      onChange={(e) => setMetros(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">
                      Precio Unitario ({divisa})
                    </label>
                    <input
                      type="number"
                      min="0"
                      className="w-full p-2.5 border border-slate-300 rounded-lg"
                      value={precioM2}
                      onChange={(e) => setPrecioM2(Number(e.target.value))}
                    />
                  </div>
                </div>
                <div className="mt-4 text-right text-sm font-bold text-slate-700">
                  Subtotal Obra: {subtotalObra.toLocaleString("es-ES", { minimumFractionDigits: 2 })}{" "}
                  {divisa}
                </div>
              </section>

              <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
                  <Users className="w-5 h-5 mr-2 text-blue-500" /> Recursos Humanos
                </h2>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">
                      Nº Trabajadores
                    </label>
                    <input
                      type="number"
                      min="0"
                      className="w-full p-2.5 border border-slate-300 rounded-lg"
                      value={trabajadores}
                      onChange={(e) => setTrabajadores(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">
                      Horas/Trabajador
                    </label>
                    <input
                      type="number"
                      min="0"
                      className="w-full p-2.5 border border-slate-300 rounded-lg"
                      value={horas}
                      onChange={(e) => setHoras(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">Coste/Hora</label>
                    <input
                      type="number"
                      min="0"
                      className="w-full p-2.5 border border-slate-300 rounded-lg"
                      value={costeHora}
                      onChange={(e) => setCosteHora(Number(e.target.value))}
                    />
                  </div>
                </div>
                <div className="mt-4 text-right text-sm font-bold text-slate-700">
                  Subtotal MO: {subtotalMo.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {divisa}
                </div>
              </section>

              <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-bold text-slate-800 flex items-center">
                    <Package className="w-5 h-5 mr-2 text-indigo-500" /> Materiales y Suministros
                  </h2>
                  <button
                    type="button"
                    onClick={addMaterial}
                    className="text-sm bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-lg font-medium flex items-center hover:bg-indigo-100"
                  >
                    <Plus className="w-4 h-4 mr-1" /> Añadir Fila
                  </button>
                </div>

                <div className="space-y-3">
                  {materiales.map((mat, i) => (
                    <div key={i} className="flex items-center space-x-2">
                      <input
                        type="text"
                        placeholder="Descripción del material..."
                        className="flex-1 p-2.5 border border-slate-300 rounded-lg text-sm"
                        value={mat.desc}
                        onChange={(e) => updateMaterial(i, "desc", e.target.value)}
                      />
                      <input
                        type="number"
                        placeholder="Cant."
                        className="w-20 p-2.5 border border-slate-300 rounded-lg text-sm"
                        value={mat.cant}
                        onChange={(e) => updateMaterial(i, "cant", Number(e.target.value))}
                      />
                      <input
                        type="number"
                        placeholder="Precio"
                        className="w-24 p-2.5 border border-slate-300 rounded-lg text-sm"
                        value={mat.precio}
                        onChange={(e) => updateMaterial(i, "precio", Number(e.target.value))}
                      />
                      <button
                        type="button"
                        onClick={() => removeMaterial(i)}
                        className="p-2.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="mt-4 text-right text-sm font-bold text-slate-700">
                  Subtotal Materiales:{" "}
                  {subtotalMateriales.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {divisa}
                </div>
              </section>
            </div>

            <div className="lg:col-span-1 space-y-6">
              <section className="bg-slate-900 text-white p-6 rounded-2xl shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl -mr-10 -mt-10" />

                <h2 className="text-lg font-bold mb-6">💰 Totalización</h2>

                <div className="space-y-4 mb-6">
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">Margen Comercial (%)</label>
                    <input
                      type="number"
                      className="w-full p-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white outline-none focus:border-blue-500"
                      value={margen}
                      onChange={(e) => setMargen(Number(e.target.value))}
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">I.V.A. Aplicable (%)</label>
                    <input
                      type="number"
                      className="w-full p-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white outline-none focus:border-blue-500"
                      value={iva}
                      onChange={(e) => setIva(Number(e.target.value))}
                    />
                  </div>
                </div>

                <div className="border-t border-slate-700 pt-4 space-y-2 text-sm">
                  <div className="flex justify-between text-slate-300">
                    <span>Base de Costes:</span>
                    <span>{subtotalBase.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {divisa}</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Base + Margen:</span>
                    <span>
                      {subtotalConMargen.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {divisa}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Impuestos (IVA):</span>
                    <span>{cuotaIva.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {divisa}</span>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-700">
                  <span className="block text-sm text-slate-400 mb-1">Presupuesto Final (IVA Inc.)</span>
                  <span className="text-3xl font-bold text-white tracking-tight">
                    {totalFinal.toLocaleString("es-ES", { minimumFractionDigits: 2 })}{" "}
                    <span className="text-lg text-blue-400">{divisa}</span>
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => void registrarPresupuesto()}
                  className="w-full mt-6 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center transition-colors shadow-lg shadow-blue-900/20"
                >
                  <Save className="w-5 h-5 mr-2" />
                  Registrar Presupuesto
                </button>
                <button
                  type="button"
                  onClick={() => void descargarCertificado()}
                  className="w-full mt-6 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center transition-colors shadow-lg shadow-emerald-900/20"
                >
                  <FileText className="w-5 h-5 mr-2" />
                  Descargar Certificado ESG (PDF)
                </button>
              </section>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
