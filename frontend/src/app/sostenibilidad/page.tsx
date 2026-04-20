"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { API_BASE, apiFetch as coreApiFetch, notifyJwtUpdated } from "@/lib/api";
import { clearAuthToken, getAuthToken, setAuthToken } from "@/lib/auth";

/** kg CO₂ / L — referencia diésel Euro 6 / marco UE (alineado con backend ReportService). */
/** ISO 14083 — diésel (mismo valor que backend ``ISO_14083_DIESEL_CO2_KG_PER_LITRE``). */
const KG_CO2_REF_ISO14083_DIESEL = 2.67;

type EmisionMensual = {
  periodo: string;
  co2_kg: number;
  litros_estimados: number;
};

type TipoMotor = "Diesel" | "Gasolina" | "Híbrido" | "Eléctrico";
type EstadoFlota = "Operativo" | "En Taller" | "Baja" | "Vendido";

type FlotaVehiculo = {
  id?: string | null;
  vehiculo: string;
  matricula: string;
  precio_compra: number;
  km_actual: number;
  estado: EstadoFlota;
  tipo_motor: TipoMotor;
};

/** Respuesta compacta de GET /eco/resumen (incl. CO2 combustible Scope 1) */
type EcoResumen = {
  n_tickets: number;
  papel_kg: number;
  co2_tickets: number;
  co2_flota: number;
  co2_combustible: number;
  co2_total: number;
};

type AmortizacionLinea = {
  anio: number;
  cuota_anual: number;
  amort_acumulada: number;
  valor_neto_contable: number;
};

type AmortizacionOut = {
  valor_inicial: number;
  vida_util_anios: number;
  valor_residual: number;
  base_amortizable: number;
  cuota_anual: number;
  cuadro: AmortizacionLinea[];
  serie_temporal: AmortizacionLinea[];
};

function formatMoneyEUR(v: number) {
  return v.toLocaleString("es-ES", { maximumFractionDigits: 2 });
}

/** Extrae nombre de archivo de Content-Disposition (RFC 5987 / quoted). */
function parseFilenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;\n]+)/i.exec(header);
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1].trim());
    } catch {
      return utf8[1].trim();
    }
  }
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted?.[1]) return quoted[1];
  const plain = /filename=([^;\s]+)/i.exec(header);
  if (plain?.[1]) return plain[1].replace(/"/g, "").trim();
  return null;
}

export default function SostenibilidadPage() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const authHeaders: Record<string, string> = token
    ? ({ Authorization: `Bearer ${token}` } as Record<string, string>)
    : {};

  const apiFetch = async (path: string, init?: RequestInit) => {
    const res = await coreApiFetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...((init?.headers as Record<string, string> | undefined) || {}),
        ...authHeaders,
      },
    });
    return res;
  };

  const login = async () => {
    setAuthError(null);
    setAuthBusy(true);
    try {
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);

      const res = await coreApiFetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: body.toString(),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Error en login");
      }

      const data = await res.json();
      setToken(data.access_token);
      try {
        setAuthToken(data.access_token);
        notifyJwtUpdated();
      } catch {
        // ignore
      }
    } catch (e: unknown) {
      setAuthError(e instanceof Error ? e.message : "Error de conexión");
    } finally {
      setAuthBusy(false);
    }
  };

  useEffect(() => {
    try {
      const saved = getAuthToken();
      if (saved) setToken(saved);
    } catch {
      // ignore
    }
  }, []);

  const [ecoResumen, setEcoResumen] = useState<EcoResumen | null>(null);
  const [ecoSim, setEcoSim] = useState<EcoResumen | null>(null);
  const [flota, setFlota] = useState<FlotaVehiculo[]>([]);
  const [loadingEco, setLoadingEco] = useState(false);
  const [loadingFlota, setLoadingFlota] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loadingCertificadoEmisiones, setLoadingCertificadoEmisiones] =
    useState(false);
  const [errorCertificadoEmisiones, setErrorCertificadoEmisiones] = useState<
    string | null
  >(null);

  const [emisionesMensuales, setEmisionesMensuales] = useState<EmisionMensual[]>([]);
  const [loadingEmisiones, setLoadingEmisiones] = useState(false);
  const [periodoHuella, setPeriodoHuella] = useState("");
  const [certHuellaBusy, setCertHuellaBusy] = useState(false);
  const [certHuellaErr, setCertHuellaErr] = useState<string | null>(null);

  const huellaComparativa = useMemo(() => {
    return emisionesMensuales.map((e) => {
      const co2_referencia_iso14083_kg = e.litros_estimados * KG_CO2_REF_ISO14083_DIESEL;
      return {
        periodo: e.periodo,
        co2_declarado_kg: e.co2_kg,
        co2_referencia_iso14083_kg,
        co2_ahorro_kg: Math.max(0, co2_referencia_iso14083_kg - e.co2_kg),
      };
    });
  }, [emisionesMensuales]);

  const tiposMotorKey = useMemo(() => {
    return flota.map((v) => v.tipo_motor).join("|");
  }, [flota]);

  useEffect(() => {
    if (!token) return;

    const load = async () => {
      setLoadingEco(true);
      setLoadingFlota(true);
      setErrorMsg(null);
      try {
        const [ecoRes, flotaRes] = await Promise.all([
          apiFetch("/eco/resumen", { method: "GET" }),
          apiFetch("/flota/inventario", { method: "GET" }),
        ]);

        if (!ecoRes.ok) throw new Error("Error cargando eco");
        if (!flotaRes.ok) throw new Error("Error cargando flota");

        const ecoRaw = await ecoRes.json();
        const eco: EcoResumen = {
          ...ecoRaw,
          co2_combustible: Number(ecoRaw.co2_combustible ?? 0),
        };
        const fl: FlotaVehiculo[] = await flotaRes.json();
        /* GET /eco/flota (ligero) — precarga opcional para validar payload reducido */
        void apiFetch("/eco/flota", { method: "GET" }).catch(() => undefined);

        setEcoResumen(eco);
        setEcoSim(eco);
        setFlota(
          fl.map((x) => ({
            id: x.id,
            vehiculo: x.vehiculo,
            matricula: x.matricula,
            precio_compra: Number(x.precio_compra),
            km_actual: Number(x.km_actual),
            estado: x.estado,
            tipo_motor: x.tipo_motor,
          }))
        );
      } catch (e: unknown) {
        setErrorMsg(e instanceof Error ? e.message : "Error cargando datos");
      } finally {
        setLoadingEco(false);
        setLoadingFlota(false);
      }
    };

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      setLoadingEmisiones(true);
      try {
        const res = await apiFetch("/eco/emisiones-mensuales", {
          credentials: "include",
        });
        if (!res.ok) return;
        const raw = (await res.json()) as EmisionMensual[];
        if (!cancelled) {
          setEmisionesMensuales(
            raw.map((r) => ({
              periodo: r.periodo,
              co2_kg: Number(r.co2_kg),
              litros_estimados: Number(r.litros_estimados),
            })),
          );
        }
      } catch {
        if (!cancelled) setEmisionesMensuales([]);
      } finally {
        if (!cancelled) setLoadingEmisiones(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (emisionesMensuales.length > 0 && !periodoHuella) {
      setPeriodoHuella(emisionesMensuales[emisionesMensuales.length - 1].periodo);
    }
  }, [emisionesMensuales, periodoHuella]);

  // Simulador: debounce cuando cambia la lista de `tipo_motor`.
  useEffect(() => {
    if (!token || !ecoResumen) return;
    if (flota.length === 0) return;

    const t = setTimeout(async () => {
      try {
        const payload = {
          n_tickets: ecoResumen.n_tickets,
          tipos_motor: flota.map((v) => v.tipo_motor),
        };

        const res = await apiFetch("/eco/simulador", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) return;
        const simRaw = await res.json();
        setEcoSim({
          ...simRaw,
          co2_combustible: Number(simRaw.co2_combustible ?? 0),
        });
      } catch {
        // best-effort
      }
    }, 350);

    return () => clearTimeout(t);
  }, [token, ecoResumen?.n_tickets, tiposMotorKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const descargarCertificado = async () => {
    if (!token || !ecoSim) return;
    const res = await apiFetch("/eco/certificado-oficial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        n_tickets: ecoSim.n_tickets,
        papel_kg: ecoSim.papel_kg,
        co2_total: ecoSim.co2_total,
      }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Certificado_Sostenibilidad_${Date.now()}.pdf`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  /**
   * GET /eco/certificate con JWT en Authorization.
   * Descarga el PDF vía blob → object URL (revocado tras la descarga).
   */
  const descargarCertificadoEmisiones = async () => {
    if (!token) {
      setErrorCertificadoEmisiones(
        "Inicia sesión para descargar el certificado de emisiones.",
      );
      return;
    }

    setLoadingCertificadoEmisiones(true);
    setErrorCertificadoEmisiones(null);

    try {
      const res = await coreApiFetch(`${API_BASE}/eco/certificate`, {
        method: "GET",
        headers: {
          Accept: "application/pdf",
        },
      });

      if (!res.ok) {
        let detail = `Error ${res.status}`;
        const text = await res.text();
        if (text) {
          try {
            const errBody = JSON.parse(text) as { detail?: unknown };
            if (errBody?.detail != null) {
              detail =
                typeof errBody.detail === "string"
                  ? errBody.detail
                  : JSON.stringify(errBody.detail);
            } else {
              detail = text.slice(0, 200);
            }
          } catch {
            detail = text.slice(0, 200);
          }
        }
        throw new Error(detail);
      }

      const blob = await res.blob();
      if (!blob.size) {
        throw new Error("El servidor devolvió un PDF vacío.");
      }

      const objectUrl = window.URL.createObjectURL(blob);
      const suggestedName =
        parseFilenameFromContentDisposition(
          res.headers.get("Content-Disposition"),
        ) ?? `Certificado_Emisiones_ESG_${Date.now()}.pdf`;

      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = suggestedName;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (e: unknown) {
      setErrorCertificadoEmisiones(
        e instanceof Error ? e.message : "No se pudo descargar el certificado.",
      );
    } finally {
      setLoadingCertificadoEmisiones(false);
    }
  };

  const descargarCertificadoHuellaPeriodo = async () => {
    if (!token || !periodoHuella) {
      setCertHuellaErr("Selecciona un periodo (YYYY-MM).");
      return;
    }
    setCertHuellaBusy(true);
    setCertHuellaErr(null);
    try {
      const res = await apiFetch(`/reports/esg/certificado-huella?periodo=${encodeURIComponent(periodoHuella)}`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/pdf" },
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t.slice(0, 160) || `Error ${res.status}`);
      }
      const blob = await res.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `Certificado_Huella_CO2_${periodoHuella}.pdf`;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (e: unknown) {
      setCertHuellaErr(e instanceof Error ? e.message : "Error al descargar");
    } finally {
      setCertHuellaBusy(false);
    }
  };

  type Tab = "eco" | "inventario" | "taller" | "finanzas";
  const [tab, setTab] = useState<Tab>("eco");

  const setTipoMotor = (idx: number, tipo: TipoMotor) => {
    setFlota((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], tipo_motor: tipo };
      return next;
    });
  };

  const setFlotaField = <K extends keyof FlotaVehiculo>(
    idx: number,
    field: K,
    value: FlotaVehiculo[K]
  ) => {
    setFlota((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const addVehiculo = () => {
    setFlota((prev) => [
      ...prev,
      {
        id: null,
        vehiculo: "",
        matricula: "",
        precio_compra: 0,
        km_actual: 0,
        estado: "Operativo",
        tipo_motor: "Diesel",
      },
    ]);
  };

  const deleteVehiculo = (idx: number) => {
    setFlota((prev) => prev.filter((_, i) => i !== idx));
  };

  const guardarInventario = async () => {
    try {
      const payload = flota.map((v) => ({
        id: v.id ?? null,
        vehiculo: v.vehiculo,
        matricula: v.matricula,
        precio_compra: v.precio_compra,
        km_actual: v.km_actual,
        estado: v.estado,
        tipo_motor: v.tipo_motor,
      }));

      const res = await apiFetch("/flota/inventario/guardar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) return;
      const saved: FlotaVehiculo[] = await res.json();
      setFlota(
        saved.map((x) => ({
          id: x.id,
          vehiculo: x.vehiculo,
          matricula: x.matricula,
          precio_compra: Number(x.precio_compra),
          km_actual: Number(x.km_actual),
          estado: x.estado,
          tipo_motor: x.tipo_motor,
        }))
      );
    } catch {
      // ignore
    }
  };

  const tiposTaller = [
    "Mecánica General",
    "Carrocería",
    "Neumáticos",
    "Electrónica",
    "ITV",
  ] as const;

  const estadosTallerInput = useMemo(() => {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const dd = String(today.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  const [vehiculoMantenimiento, setVehiculoMantenimiento] = useState("");
  const [fechaMantenimiento, setFechaMantenimiento] =
    useState(estadosTallerInput);
  const [tipoMantenimiento, setTipoMantenimiento] =
    useState<(typeof tiposTaller)[number]>("Mecánica General");
  const [costeMantenimiento, setCosteMantenimiento] = useState<number>(0);
  const [kmMantenimiento, setKmMantenimiento] = useState<number>(0);
  const [descMantenimiento, setDescMantenimiento] = useState("");
  const [mantenimientoBusy, setMantenimientoBusy] = useState(false);
  const [mantenimientoError, setMantenimientoError] = useState<string | null>(
    null
  );

  const crearMantenimiento = async () => {
    if (!token) return;
    if (!vehiculoMantenimiento) return;
    setMantenimientoBusy(true);
    setMantenimientoError(null);
    try {
      const res = await apiFetch("/flota/mantenimiento", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vehiculo: vehiculoMantenimiento,
          fecha: fechaMantenimiento,
          tipo: tipoMantenimiento,
          coste: costeMantenimiento,
          kilometros: kmMantenimiento,
          descripcion: descMantenimiento || null,
        }),
      });
      if (!res.ok) throw new Error("Error creando mantenimiento");
      setDescMantenimiento("");
    } catch (e: unknown) {
      setMantenimientoError(e instanceof Error ? e.message : "Error");
    } finally {
      setMantenimientoBusy(false);
    }
  };

  const matriculas = useMemo(() => {
    const uniq = Array.from(new Set(flota.map((v) => v.matricula).filter(Boolean)));
    return uniq;
  }, [flota]);

  const [matriculaSeleccionada, setMatriculaSeleccionada] = useState<string>("");
  const [vidaUtil, setVidaUtil] = useState<number>(5);
  const [valorResidual, setValorResidual] = useState<number>(0);
  const [amortBusy, setAmortBusy] = useState(false);
  const [amortizacion, setAmortizacion] = useState<AmortizacionOut | null>(null);

  useEffect(() => {
    if (matriculas.length === 0) {
      setMatriculaSeleccionada("");
      setAmortizacion(null);
      return;
    }
    if (!matriculaSeleccionada) {
      setMatriculaSeleccionada(matriculas[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matriculas.join("|")]);

  useEffect(() => {
    if (!token || !ecoResumen) return;
    if (!matriculaSeleccionada) return;
    const v = flota.find((x) => x.matricula === matriculaSeleccionada);
    if (!v) return;

    const t = setTimeout(async () => {
      setAmortBusy(true);
      try {
        const res = await apiFetch("/flota/amortizacion-lineal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            valor_inicial: v.precio_compra,
            vida_util_anios: vidaUtil,
            valor_residual: valorResidual,
          }),
        });
        if (!res.ok) return;
        const out: AmortizacionOut = await res.json();
        setAmortizacion(out);
      } catch {
        // ignore
      } finally {
        setAmortBusy(false);
      }
    }, 250);

    return () => clearTimeout(t);
  }, [token, matriculaSeleccionada, vidaUtil, valorResidual, flota, ecoResumen]);

  const amortChart = useMemo(() => {
    if (!amortizacion) return [];
    const serie =
      amortizacion.serie_temporal?.length
        ? amortizacion.serie_temporal
        : amortizacion.cuadro;
    return serie.map((l) => ({
      year: `Año ${l.anio}`,
      vnc: l.valor_neto_contable,
    }));
  }, [amortizacion]);

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 font-sans flex items-center justify-center p-6">
        <div className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-4">
          <h1 className="text-2xl font-bold text-slate-800">Login</h1>
          <p className="text-sm text-slate-500">
            Necesitas autenticación para consumir `resumen eco` y el editor de flota.
          </p>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-600">Usuario</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full p-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-600">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
          {authError && <div className="text-sm text-red-600">{authError}</div>}
          <button
            onClick={login}
            disabled={authBusy}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center transition-colors shadow-lg shadow-blue-900/20 disabled:opacity-60"
          >
            {authBusy ? "Autenticando..." : "Entrar"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-50 font-sans">
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <span className="text-white font-bold text-lg tracking-tight">
            AB Logistics OS
          </span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          <button
            onClick={() => setTab("eco")}
            className={
              tab === "eco"
                ? "w-full flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg transition-colors"
                : "w-full text-left flex items-center px-3 py-2.5 hover:bg-slate-800 hover:text-white rounded-lg transition-colors"
            }
          >
            Sostenibilidad
          </button>
          <button
            onClick={() => setTab("inventario")}
            className={
              tab === "inventario"
                ? "w-full flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg transition-colors"
                : "w-full text-left flex items-center px-3 py-2.5 hover:bg-slate-800 hover:text-white rounded-lg transition-colors"
            }
          >
            Simulador de Flota
          </button>
          <button
            onClick={() => setTab("taller")}
            className={
              tab === "taller"
                ? "w-full flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg transition-colors"
                : "w-full text-left flex items-center px-3 py-2.5 hover:bg-slate-800 hover:text-white rounded-lg transition-colors"
            }
          >
            Libro de Taller
          </button>
          <button
            onClick={() => setTab("finanzas")}
            className={
              tab === "finanzas"
                ? "w-full flex items-center px-3 py-2.5 bg-blue-600/10 text-blue-400 rounded-lg transition-colors"
                : "w-full text-left flex items-center px-3 py-2.5 hover:bg-slate-800 hover:text-white rounded-lg transition-colors"
            }
          >
            Amortización
          </button>
        </nav>
      </aside>

      <main className="flex-1 flex flex-col overflow-y-auto">
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 z-10 sticky top-0">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
            Sostenibilidad y Simulador
          </h1>
          <button
            onClick={() => {
              setToken(null);
              try {
                clearAuthToken();
              } catch {
                // ignore
              }
            }}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Cerrar sesión
          </button>
        </header>

        <div className="p-8 max-w-7xl mx-auto space-y-6 flex-1">
          {errorMsg && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {errorMsg}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: eco summary + chart */}
            <section className="lg:col-span-1 space-y-4">
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                <h2 className="text-lg font-bold text-slate-800 mb-1">
                  Resumen ESG
                </h2>
                <p className="text-sm text-slate-500">
                  Resumen ESG: tickets, flota y CO2 combustible (gastos categoría
                  COMBUSTIBLE, Scope 1).
                </p>
                {loadingEco || !ecoSim ? (
                  <div className="mt-4 text-sm text-slate-500">
                    Cargando...
                  </div>
                ) : (
                  <>
                    <div className="mt-5 grid grid-cols-1 gap-3">
                      <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                        <div className="text-sm text-slate-500">Tickets digitalizados</div>
                        <div className="text-3xl font-bold text-slate-800">
                          {ecoSim.n_tickets}
                        </div>
                      </div>
                      <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                        <div className="text-sm text-slate-500">
                          Papel ahorrado (Kg)
                        </div>
                        <div className="text-3xl font-bold text-slate-800">
                          {ecoSim.papel_kg.toFixed(3)}
                        </div>
                      </div>
                      <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                        <div className="text-sm text-slate-500">
                          CO2 combustible (kg, Scope 1)
                        </div>
                        <div className="text-3xl font-bold text-slate-800">
                          {(ecoSim.co2_combustible ?? 0).toFixed(2)}
                        </div>
                      </div>
                      <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                        <div className="text-sm text-slate-500">
                          CO2 total (kg)
                        </div>
                        <div className="text-3xl font-bold text-slate-800">
                          {ecoSim.co2_total.toFixed(2)}
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 h-80 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={[
                            {
                              label: "CO2 (kg)",
                              tickets: ecoSim.co2_tickets,
                              flota: ecoSim.co2_flota,
                              combustible: ecoSim.co2_combustible ?? 0,
                            },
                          ]}
                          margin={{ top: 20, right: 10, left: -10, bottom: 10 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                          <XAxis dataKey="label" stroke="#64748b" tickLine={false} axisLine={false} />
                          <YAxis stroke="#64748b" tickLine={false} axisLine={false} />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="tickets" name="CO2 tickets" fill="#ef4444" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="flota" name="CO2 flota" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="combustible" name="CO2 combustible" fill="#22c55e" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    {errorCertificadoEmisiones && (
                      <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-100 px-3 py-2 rounded-lg">
                        {errorCertificadoEmisiones}
                      </div>
                    )}

                    <div className="mt-6 flex flex-col sm:flex-row gap-3">
                      <button
                        type="button"
                        disabled={loadingCertificadoEmisiones || !token}
                        onClick={() => void descargarCertificadoEmisiones()}
                        className="flex-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3 rounded-xl transition-colors"
                      >
                        {loadingCertificadoEmisiones
                          ? "Generando PDF…"
                          : "Certificado emisiones (PDF)"}
                      </button>
                      <button
                        type="button"
                        onClick={() => void descargarCertificado()}
                        className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition-colors shadow-lg shadow-emerald-900/20"
                      >
                        Certificado legacy
                      </button>
                    </div>
                  </>
                )}
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm mt-4">
                <h2 className="text-lg font-bold text-[#0b1224] mb-1">
                  Certificados de huella de carbono (ISO 14083)
                </h2>
                <p className="text-sm text-slate-500 mb-4">
                  Comparativa Scope 1 (combustible): emisiones declaradas vs referencia diésel{" "}
                  <span className="font-mono text-xs">{KG_CO2_REF_ISO14083_DIESEL} kg CO₂/L</span>. Descarga PDF
                  por periodo vía <code className="text-xs">GET /reports/esg/certificado-huella</code>.
                </p>
                {loadingEmisiones ? (
                  <p className="text-sm text-slate-500">Cargando series mensuales…</p>
                ) : huellaComparativa.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    Sin gastos categoría COMBUSTIBLE — no hay series para comparar.
                  </p>
                ) : (
                  <>
                    <div className="h-64 w-full mb-4">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={huellaComparativa}
                          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                          <XAxis dataKey="periodo" tick={{ fontSize: 10, fill: "#64748b" }} />
                          <YAxis tick={{ fontSize: 10, fill: "#64748b" }} />
                          <Tooltip />
                          <Legend />
                          <Bar
                            dataKey="co2_referencia_iso14083_kg"
                            name="Referencia ISO 14083 (kg)"
                            fill="#0b1224"
                            radius={[4, 4, 0, 0]}
                          />
                          <Bar
                            dataKey="co2_declarado_kg"
                            name="Declarado (kg)"
                            fill="#2563eb"
                            radius={[4, 4, 0, 0]}
                          />
                          <Bar
                            dataKey="co2_ahorro_kg"
                            name="Ahorro estimado (kg)"
                            fill="#22c55e"
                            radius={[4, 4, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-end">
                      <div className="flex-1">
                        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
                          periodo (YYYY-MM)
                        </label>
                        <select
                          value={periodoHuella}
                          onChange={(e) => setPeriodoHuella(e.target.value)}
                          className="w-full p-2.5 border border-slate-300 rounded-lg bg-white outline-none text-sm"
                        >
                          {emisionesMensuales.map((e) => (
                            <option key={e.periodo} value={e.periodo}>
                              {e.periodo}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        disabled={certHuellaBusy || !periodoHuella}
                        onClick={() => void descargarCertificadoHuellaPeriodo()}
                        className="sm:self-stretch px-5 py-2.5 rounded-xl font-bold text-white bg-[#2563eb] hover:bg-[#1d4ed8] disabled:opacity-50 shadow-md shadow-blue-900/20"
                      >
                        {certHuellaBusy ? "Generando…" : "Descargar certificado PDF"}
                      </button>
                    </div>
                    {certHuellaErr && (
                      <p className="mt-2 text-sm text-red-600">{certHuellaErr}</p>
                    )}
                  </>
                )}
              </div>
            </section>

            {/* Right: eco simulator + tabs quick edit */}
            <section className="lg:col-span-2 space-y-4">
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                <h2 className="text-lg font-bold text-slate-800 mb-1">
                  Simulador de Flota (motor)
                </h2>
                <p className="text-sm text-slate-500 mb-4">
                  Edita `tipo_motor` para recalcular el CO2 de flota.
                </p>

                {loadingFlota && flota.length === 0 ? (
                  <div className="text-sm text-slate-500">Cargando flota...</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 text-sm text-slate-500 font-medium bg-white">
                          <th className="px-3 py-3">Vehículo</th>
                          <th className="px-3 py-3">Matrícula</th>
                          <th className="px-3 py-3">Motor</th>
                        </tr>
                      </thead>
                      <tbody className="text-sm">
                        {flota.map((v, idx) => (
                          <tr key={v.id ?? `new-${idx}`} className="border-b border-slate-50 hover:bg-slate-50/80">
                            <td className="px-3 py-3 text-slate-700 font-medium">{v.vehiculo}</td>
                            <td className="px-3 py-3 text-slate-700">{v.matricula}</td>
                            <td className="px-3 py-3">
                              <select
                                value={v.tipo_motor}
                                onChange={(e) =>
                                  setTipoMotor(idx, e.target.value as TipoMotor)
                                }
                                className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                              >
                                <option value="Diesel">Diesel</option>
                                <option value="Gasolina">Gasolina</option>
                                <option value="Híbrido">Híbrido</option>
                                <option value="Eléctrico">Eléctrico</option>
                              </select>
                            </td>
                          </tr>
                        ))}
                        {flota.length === 0 && (
                          <tr>
                            <td className="px-3 py-4 text-sm text-slate-500" colSpan={3}>
                              No hay vehículos registrados.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Fleet simulator tabs */}
              <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm">
                <div className="flex justify-between items-center mb-4">
                  <div>
                    <div className="text-sm text-slate-500">Secciones</div>
                    <div className="text-lg font-bold text-slate-800">Simulador de Flota</div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setTab("inventario")}
                      className={
                        tab === "inventario"
                          ? "px-3 py-2 rounded-lg bg-blue-50 text-blue-700 font-medium"
                          : "px-3 py-2 rounded-lg bg-slate-50 text-slate-600 hover:bg-slate-100 font-medium"
                      }
                    >
                      Inventario
                    </button>
                    <button
                      onClick={() => setTab("taller")}
                      className={
                        tab === "taller"
                          ? "px-3 py-2 rounded-lg bg-blue-50 text-blue-700 font-medium"
                          : "px-3 py-2 rounded-lg bg-slate-50 text-slate-600 hover:bg-slate-100 font-medium"
                      }
                    >
                      Taller
                    </button>
                    <button
                      onClick={() => setTab("finanzas")}
                      className={
                        tab === "finanzas"
                          ? "px-3 py-2 rounded-lg bg-blue-50 text-blue-700 font-medium"
                          : "px-3 py-2 rounded-lg bg-slate-50 text-slate-600 hover:bg-slate-100 font-medium"
                      }
                    >
                      Finanzas
                    </button>
                  </div>
                </div>

                {tab === "inventario" && (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-md font-bold text-slate-800">
                        Inventario de Vehículos
                      </h3>
                      <div className="flex gap-2">
                        <button
                          onClick={addVehiculo}
                          className="px-3 py-2 rounded-lg bg-indigo-50 text-indigo-700 font-medium hover:bg-indigo-100"
                        >
                          Añadir
                        </button>
                        <button
                          onClick={guardarInventario}
                          className="px-3 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500"
                        >
                          Guardar cambios
                        </button>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-100 text-sm text-slate-500 font-medium bg-white">
                            <th className="px-3 py-3">ID</th>
                            <th className="px-3 py-3">Vehículo</th>
                            <th className="px-3 py-3">Matrícula</th>
                            <th className="px-3 py-3">Coste adq.</th>
                            <th className="px-3 py-3">Km actual</th>
                            <th className="px-3 py-3">Estado</th>
                            <th className="px-3 py-3">Motor</th>
                            <th className="px-3 py-3">Acción</th>
                          </tr>
                        </thead>
                        <tbody className="text-sm">
                          {flota.map((v, idx) => (
                            <tr
                              key={v.id ?? `new-${idx}`}
                              className="border-b border-slate-50 hover:bg-slate-50/80"
                            >
                              <td className="px-3 py-3 text-slate-500">{v.id || "-"}</td>
                              <td className="px-3 py-3">
                                <input
                                  value={v.vehiculo}
                                  onChange={(e) =>
                                    setFlotaField(idx, "vehiculo", e.target.value)
                                  }
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={v.matricula}
                                  onChange={(e) =>
                                    setFlotaField(idx, "matricula", e.target.value)
                                  }
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  type="number"
                                  value={v.precio_compra}
                                  onChange={(e) =>
                                    setFlotaField(
                                      idx,
                                      "precio_compra",
                                      Number(e.target.value)
                                    )
                                  }
                                  min={0}
                                  step={1}
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  type="number"
                                  value={v.km_actual}
                                  onChange={(e) =>
                                    setFlotaField(idx, "km_actual", Number(e.target.value))
                                  }
                                  min={0}
                                  step={1}
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <select
                                  value={v.estado}
                                  onChange={(e) =>
                                    setFlotaField(
                                      idx,
                                      "estado",
                                      e.target.value as EstadoFlota
                                    )
                                  }
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                >
                                  <option value="Operativo">Operativo</option>
                                  <option value="En Taller">En Taller</option>
                                  <option value="Baja">Baja</option>
                                  <option value="Vendido">Vendido</option>
                                </select>
                              </td>
                              <td className="px-3 py-3">
                                <select
                                  value={v.tipo_motor}
                                  onChange={(e) =>
                                    setFlotaField(
                                      idx,
                                      "tipo_motor",
                                      e.target.value as TipoMotor
                                    )
                                  }
                                  className="w-full p-2 border border-slate-300 rounded-lg bg-white outline-none"
                                >
                                  <option value="Diesel">Diesel</option>
                                  <option value="Gasolina">Gasolina</option>
                                  <option value="Híbrido">Híbrido</option>
                                  <option value="Eléctrico">Eléctrico</option>
                                </select>
                              </td>
                              <td className="px-3 py-3">
                                <button
                                  onClick={() => deleteVehiculo(idx)}
                                  className="text-sm text-red-600 hover:text-red-700 font-medium"
                                >
                                  Eliminar
                                </button>
                              </td>
                            </tr>
                          ))}
                          {flota.length === 0 && (
                            <tr>
                              <td colSpan={8} className="px-3 py-4 text-sm text-slate-500">
                                No hay vehículos.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {tab === "taller" && (
                  <div className="space-y-4">
                    <h3 className="text-md font-bold text-slate-800">
                      Libro de Taller
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Vehículo (matrícula)
                        </label>
                        <select
                          value={vehiculoMantenimiento}
                          onChange={(e) => setVehiculoMantenimiento(e.target.value)}
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                        >
                          <option value="">Seleccionar...</option>
                          {flota.map((v) => (
                            <option key={v.id ?? v.matricula} value={v.matricula}>
                              {v.matricula} - {v.vehiculo}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Fecha entrada
                        </label>
                        <input
                          type="date"
                          value={fechaMantenimiento}
                          onChange={(e) => setFechaMantenimiento(e.target.value)}
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Tipo Intervención
                        </label>
                        <select
                          value={tipoMantenimiento}
                          onChange={(e) =>
                            setTipoMantenimiento(e.target.value as (typeof tiposTaller)[number])
                          }
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                        >
                          {tiposTaller.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Coste factura (€)
                        </label>
                        <input
                          type="number"
                          min={0}
                          step={10}
                          value={costeMantenimiento}
                          onChange={(e) =>
                            setCosteMantenimiento(Number(e.target.value))
                          }
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Kilómetros al entrar
                        </label>
                        <input
                          type="number"
                          min={0}
                          value={kmMantenimiento}
                          onChange={(e) => setKmMantenimiento(Number(e.target.value))}
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                          Detalle de trabajos
                        </label>
                        <textarea
                          value={descMantenimiento}
                          onChange={(e) => setDescMantenimiento(e.target.value)}
                          className="w-full p-2.5 border border-slate-300 rounded-lg outline-none min-h-[100px]"
                        />
                      </div>
                    </div>

                    {mantenimientoError && (
                      <div className="text-sm text-red-600">{mantenimientoError}</div>
                    )}

                    <button
                      onClick={crearMantenimiento}
                      disabled={mantenimientoBusy}
                      className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-xl transition-colors shadow-lg shadow-blue-900/20 disabled:opacity-60"
                    >
                      {mantenimientoBusy ? "Guardando..." : "Registrar historial"}
                    </button>
                  </div>
                )}

                {tab === "finanzas" && (
                  <div className="space-y-4">
                    <h3 className="text-md font-bold text-slate-800">
                      Plan de Amortización
                    </h3>

                    {matriculas.length === 0 ? (
                      <div className="text-sm text-slate-500">
                        No hay flota para amortizar.
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="md:col-span-1">
                            <label className="block text-sm font-medium text-slate-600 mb-1">
                              Analizar activo
                            </label>
                            <select
                              value={matriculaSeleccionada}
                              onChange={(e) =>
                                setMatriculaSeleccionada(e.target.value)
                              }
                              className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                            >
                              {matriculas.map((m) => (
                                <option key={m} value={m}>
                                  {m}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-slate-600 mb-1">
                              Vida útil (años)
                            </label>
                            <input
                              type="number"
                              min={1}
                              step={1}
                              value={vidaUtil}
                              onChange={(e) => setVidaUtil(Number(e.target.value))}
                              className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-slate-600 mb-1">
                              Valor residual (€)
                            </label>
                            <input
                              type="number"
                              min={0}
                              step={10}
                              value={valorResidual}
                              onChange={(e) =>
                                setValorResidual(Number(e.target.value))
                              }
                              className="w-full p-2.5 border border-slate-300 rounded-lg outline-none"
                            />
                          </div>
                        </div>

                        {amortBusy || !amortizacion ? (
                          <div className="text-sm text-slate-500">Calculando...</div>
                        ) : (
                          <>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                                <div className="text-sm text-slate-500">
                                  Valor inicial
                                </div>
                                <div className="text-2xl font-bold text-slate-800">
                                  {formatMoneyEUR(amortizacion.valor_inicial)} €
                                </div>
                              </div>
                              <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                                <div className="text-sm text-slate-500">
                                  Amortización anual
                                </div>
                                <div className="text-2xl font-bold text-slate-800">
                                  {formatMoneyEUR(amortizacion.cuota_anual)} €
                                </div>
                              </div>
                              <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl">
                                <div className="text-sm text-slate-500">
                                  Valor residual
                                </div>
                                <div className="text-2xl font-bold text-slate-800">
                                  {formatMoneyEUR(amortizacion.valor_residual)} €
                                </div>
                              </div>
                            </div>

                            <div className="h-72 w-full">
                              <ResponsiveContainer width="100%" height="100%">
                                <AreaChart
                                  data={amortChart}
                                  margin={{ top: 15, right: 10, left: -10, bottom: 5 }}
                                >
                                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                                  <XAxis dataKey="year" stroke="#64748b" tickLine={false} axisLine={false} />
                                  <YAxis stroke="#64748b" tickLine={false} axisLine={false} />
                                  <Tooltip />
                                  <Legend />
                                  <Area
                                    type="monotone"
                                    dataKey="vnc"
                                    name="Valor Neto Contable (VNC)"
                                    stroke="#1d4ed8"
                                    fill="#93c5fd"
                                    fillOpacity={0.35}
                                    strokeWidth={2}
                                  />
                                </AreaChart>
                              </ResponsiveContainer>
                            </div>

                            <div className="overflow-x-auto">
                              <table className="w-full text-left border-collapse">
                                <thead>
                                  <tr className="border-b border-slate-100 text-sm text-slate-500 font-medium bg-white">
                                    <th className="px-3 py-3">Año</th>
                                    <th className="px-3 py-3">Cuota anual</th>
                                    <th className="px-3 py-3">Amort. acumulada</th>
                                    <th className="px-3 py-3">VNC</th>
                                  </tr>
                                </thead>
                                <tbody className="text-sm">
                                  {amortizacion.cuadro.map((l) => (
                                    <tr key={l.anio} className="border-b border-slate-50 hover:bg-slate-50/80">
                                      <td className="px-3 py-3 text-slate-700 font-medium">
                                        Año {l.anio}
                                      </td>
                                      <td className="px-3 py-3 text-slate-700">
                                        {formatMoneyEUR(l.cuota_anual)} €
                                      </td>
                                      <td className="px-3 py-3 text-slate-700">
                                        {formatMoneyEUR(l.amort_acumulada)} €
                                      </td>
                                      <td className="px-3 py-3 text-slate-700">
                                        {formatMoneyEUR(l.valor_neto_contable)} €
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

