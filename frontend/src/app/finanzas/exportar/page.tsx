"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { downloadAccountingExport, type ExportContableTipo, API_BASE, api, apiFetch, type Factura } from "@/lib/api";
import { exportToExcel, exportToPDF } from "@/lib/exportUtils";
import { PorteSchema, type Porte } from "@/lib/schemas";

function defaultDates() {
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth(), 1);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { inicio: iso(start), fin: iso(end) };
}

type TabId = "portes" | "facturas" | "clientes";

type ClienteRow = {
  id: string;
  nombre: string;
  nif?: string | null;
  email?: string | null;
  telefono?: string | null;
};

const PORTES_PDF_COLUMNS = [
  "Id",
  "Fecha",
  "ClienteId",
  "ClienteNombre",
  "Origen",
  "Destino",
  "Estado",
  "PrecioPactado",
  "KmEstimados",
  "FacturaId",
] as const;

const FACTURAS_PDF_COLUMNS = [
  "Id",
  "NumeroFactura",
  "TipoFactura",
  "FechaEmision",
  "TotalFactura",
  "ClienteNombre",
  "AeatSifEstado",
  "HashRegistro",
] as const;

const CLIENTES_PDF_COLUMNS = ["Id", "Nombre", "Nif", "Email", "Telefono"] as const;

function porteToExportRow(p: Porte) {
  return {
    id: p.id,
    fecha: p.fecha,
    cliente_id: p.cliente_id ?? null,
    cliente_nombre: p.cliente_nombre ?? null,
    origen: p.origen,
    destino: p.destino,
    estado: p.estado,
    precio_pactado: p.precio_pactado ?? null,
    km_estimados: p.km_estimados ?? null,
    factura_id: p.factura_id ?? null,
  };
}

function porteToPdfRow(p: Porte): Record<string, unknown> {
  return {
    Id: p.id,
    Fecha: p.fecha,
    ClienteId: p.cliente_id ?? "",
    ClienteNombre: p.cliente_nombre ?? "",
    Origen: p.origen,
    Destino: p.destino,
    Estado: p.estado,
    PrecioPactado: p.precio_pactado ?? "",
    KmEstimados: p.km_estimados ?? "",
    FacturaId: p.factura_id ?? "",
  };
}

function facturaToExportRow(f: Factura) {
  return {
    id: f.id,
    numero_factura: f.numero_factura ?? null,
    tipo_factura: f.tipo_factura ?? null,
    fecha_emision: f.fecha_emision ?? null,
    total_factura: f.total_factura ?? null,
    cliente_nombre: f.cliente_nombre ?? null,
    aeat_sif_estado: f.aeat_sif_estado ?? null,
    hash_registro: f.hash_registro ?? null,
  };
}

function facturaToPdfRow(f: Factura): Record<string, unknown> {
  return {
    Id: f.id,
    NumeroFactura: f.numero_factura ?? "",
    TipoFactura: f.tipo_factura ?? "",
    FechaEmision: f.fecha_emision ? String(f.fecha_emision).slice(0, 10) : "",
    TotalFactura: f.total_factura ?? "",
    ClienteNombre: f.cliente_nombre ?? "",
    AeatSifEstado: f.aeat_sif_estado ?? "",
    HashRegistro: f.hash_registro ?? "",
  };
}

function clienteToExportRow(c: ClienteRow) {
  return {
    id: c.id,
    nombre: c.nombre,
    nif: c.nif ?? null,
    email: c.email ?? null,
    telefono: c.telefono ?? null,
  };
}

function clienteToPdfRow(c: ClienteRow): Record<string, unknown> {
  return {
    Id: c.id,
    Nombre: c.nombre,
    Nif: c.nif ?? "",
    Email: c.email ?? "",
    Telefono: c.telefono ?? "",
  };
}

function matchesQuery(haystack: string, q: string): boolean {
  if (!q) return true;
  return haystack.toLowerCase().includes(q);
}

export default function ExportarContablePage() {
  const defaults = useMemo(() => defaultDates(), []);
  const [inicio, setInicio] = useState(defaults.inicio);
  const [fin, setFin] = useState(defaults.fin);
  const [tipo, setTipo] = useState<ExportContableTipo>("ventas");
  const [loading, setLoading] = useState<"csv" | "excel" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [tab, setTab] = useState<TabId>("portes");
  const [filterText, setFilterText] = useState("");
  const [portes, setPortes] = useState<Porte[]>([]);
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [clientes, setClientes] = useState<ClienteRow[]>([]);
  const [loadPortes, setLoadPortes] = useState(true);
  const [loadFacturas, setLoadFacturas] = useState(true);
  const [loadClientes, setLoadClientes] = useState(true);
  const [dataError, setDataError] = useState<string | null>(null);
  const [exportBusy, setExportBusy] = useState<"excel" | "pdf" | null>(null);

  const fetchPortes = useCallback(async () => {
    setLoadPortes(true);
    setDataError(null);
    try {
      const data = await apiFetch(`${API_BASE}/portes/`, { method: "GET" }, PorteSchema.array());
      setPortes(data.filter((p) => p.estado === "pendiente"));
    } catch (e: unknown) {
      setPortes([]);
      setDataError(e instanceof Error ? e.message : "Error al cargar portes");
    } finally {
      setLoadPortes(false);
    }
  }, []);

  const fetchFacturas = useCallback(async () => {
    setLoadFacturas(true);
    setDataError(null);
    try {
      setFacturas(await api.facturas.getAll());
    } catch {
      setFacturas([]);
      setDataError("Error al cargar facturas");
    } finally {
      setLoadFacturas(false);
    }
  }, []);

  const fetchClientes = useCallback(async () => {
    setLoadClientes(true);
    setDataError(null);
    try {
      const res = await apiFetch(`${API_BASE}/clientes/`, { credentials: "include" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err?.detail === "string" ? err.detail : `HTTP ${res.status}`);
      }
      const data = (await res.json()) as ClienteRow[];
      setClientes(data.filter((r) => r.nombre));
    } catch (e: unknown) {
      setClientes([]);
      setDataError(e instanceof Error ? e.message : "Error al cargar clientes");
    } finally {
      setLoadClientes(false);
    }
  }, []);

  useEffect(() => {
    void fetchPortes();
    void fetchFacturas();
    void fetchClientes();
  }, [fetchPortes, fetchFacturas, fetchClientes]);

  const q = filterText.trim().toLowerCase();

  const filteredPortes = useMemo(() => {
    if (!q) return portes;
    return portes.filter((p) => {
      const blob = [
        p.id,
        p.fecha,
        p.cliente_id,
        p.cliente_nombre,
        p.origen,
        p.destino,
        p.estado,
        String(p.precio_pactado ?? ""),
      ]
        .filter(Boolean)
        .join(" ");
      return matchesQuery(blob, q);
    });
  }, [portes, q]);

  const filteredFacturas = useMemo(() => {
    if (!q) return facturas;
    return facturas.filter((f) => {
      const blob = [
        String(f.id),
        f.numero_factura,
        f.tipo_factura,
        f.fecha_emision,
        String(f.total_factura ?? ""),
        f.cliente_nombre,
        f.aeat_sif_estado,
        f.hash_registro,
      ]
        .filter(Boolean)
        .join(" ");
      return matchesQuery(blob, q);
    });
  }, [facturas, q]);

  const filteredClientes = useMemo(() => {
    if (!q) return clientes;
    return clientes.filter((c) => {
      const blob = [c.id, c.nombre, c.nif, c.email, c.telefono].filter(Boolean).join(" ");
      return matchesQuery(blob, q);
    });
  }, [clientes, q]);

  const tabLoading =
    tab === "portes" ? loadPortes : tab === "facturas" ? loadFacturas : loadClientes;

  const currentFiltered =
    tab === "portes" ? filteredPortes : tab === "facturas" ? filteredFacturas : filteredClientes;

  const exportDisabled = tabLoading || exportBusy !== null || currentFiltered.length === 0;

  const stamp = useMemo(() => {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  }, []);

  async function run(fmt: "csv" | "excel") {
    setError(null);
    setLoading(fmt);
    try {
      await downloadAccountingExport({
        fecha_inicio: inicio,
        fecha_fin: fin,
        tipo,
        formato: fmt,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setLoading(null);
    }
  }

  const handleExportExcel = async () => {
    if (tabLoading || exportBusy !== null || currentFiltered.length === 0) return;
    setExportBusy("excel");
    setDataError(null);
    try {
      if (tab === "portes") {
        exportToExcel(
          filteredPortes.map(porteToExportRow),
          `portes-pendientes-${stamp}.xlsx`,
        );
      } else if (tab === "facturas") {
        exportToExcel(
          filteredFacturas.map(facturaToExportRow),
          `facturas-${stamp}.xlsx`,
        );
      } else {
        exportToExcel(
          filteredClientes.map(clienteToExportRow),
          `clientes-${stamp}.xlsx`,
        );
      }
    } catch (e: unknown) {
      setDataError(e instanceof Error ? e.message : "Error al exportar a Excel");
    } finally {
      setExportBusy(null);
    }
  };

  const handleExportPdf = async () => {
    if (tabLoading || exportBusy !== null || currentFiltered.length === 0) return;
    setExportBusy("pdf");
    setDataError(null);
    try {
      if (tab === "portes") {
        await exportToPDF(
          filteredPortes.map(porteToPdfRow),
          [...PORTES_PDF_COLUMNS],
          "Portes pendientes",
          `portes-pendientes-${stamp}.pdf`,
        );
      } else if (tab === "facturas") {
        await exportToPDF(
          filteredFacturas.map(facturaToPdfRow),
          [...FACTURAS_PDF_COLUMNS],
          "Facturas emitidas",
          `facturas-${stamp}.pdf`,
        );
      } else {
        await exportToPDF(
          filteredClientes.map(clienteToPdfRow),
          [...CLIENTES_PDF_COLUMNS],
          "Clientes activos",
          `clientes-${stamp}.pdf`,
        );
      }
    } catch (e: unknown) {
      setDataError(e instanceof Error ? e.message : "Error al exportar a PDF");
    } finally {
      setExportBusy(null);
    }
  };

  return (
    <AppShell active="exportar">
      <RoleGuard
        allowedRoles={["owner"]}
        fallback={
          <main className="p-8">
            <p className="text-slate-500">
              La exportación contable solo está disponible para administradores.
            </p>
          </main>
        }
      >
        <header className="h-16 ab-header border-b border-slate-800/80 flex items-center justify-between px-8 z-10 shrink-0 bg-[#0a0f1a]/90 backdrop-blur-sm">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
              Exportación contable
            </h1>
            <p className="text-sm text-slate-500">
              Diario de ventas / compras (CSV para A3/Sage, Excel con hojas separadas)
            </p>
          </div>
        </header>

        <main
          className="p-8 flex-1 overflow-y-auto max-w-3xl mx-auto w-full space-y-10"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(37, 99, 235, 0.08), transparent), #020617",
          }}
        >
          {error && (
            <div
              className="rounded-xl border px-4 py-3 text-sm text-red-200"
              style={{
                background: "rgba(127, 29, 29, 0.25)",
                borderColor: "rgba(248, 113, 113, 0.35)",
              }}
            >
              {error}
            </div>
          )}

          <div
            className="rounded-2xl border border-slate-700/80 p-6 space-y-6"
            style={{
              background:
                "linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(2, 6, 23, 0.98) 100%)",
            }}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Fecha inicio
                </span>
                <input
                  type="date"
                  value={inicio}
                  onChange={(e) => setInicio(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Fecha fin
                </span>
                <input
                  type="date"
                  value={fin}
                  onChange={(e) => setFin(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
                />
              </label>
            </div>

            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Tipo de diario
              </span>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as ExportContableTipo)}
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100"
              >
                <option value="ventas">Ventas (facturas emitidas)</option>
                <option value="compras">Gastos / compras</option>
                <option value="ambos">Ventas y compras</option>
              </select>
            </label>

            <p className="text-xs text-slate-500 leading-relaxed">
              Los importes se redondean en servidor a 2 decimales (motor fiat). Si eliges ambos en
              CSV, se descarga un ZIP con dos archivos.
            </p>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => void run("excel")}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5"
              >
                {loading === "excel" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="w-4 h-4" />
                )}
                Descargar Excel
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => void run("csv")}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/90 hover:bg-slate-700 disabled:opacity-50 text-slate-100 text-sm font-semibold px-4 py-2.5"
              >
                {loading === "csv" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                Descargar CSV (A3 / Sage)
              </button>
            </div>
          </div>

          {/* Data center: tablas operativas */}
          <div
            className="rounded-2xl border border-slate-700/80 p-6 space-y-5"
            style={{
              background:
                "linear-gradient(145deg, rgba(15, 23, 42, 0.95) 0%, rgba(2, 6, 23, 0.98) 100%)",
            }}
          >
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">Data center</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Portes, facturas y clientes: exporta el mismo conjunto que ves filtrado en la tabla.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  void fetchPortes();
                  void fetchFacturas();
                  void fetchClientes();
                }}
                disabled={loadPortes || loadFacturas || loadClientes}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/90 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-700 disabled:opacity-50 shrink-0"
              >
                <RefreshCw
                  className={`w-4 h-4 ${loadPortes || loadFacturas || loadClientes ? "animate-spin" : ""}`}
                />
                Actualizar datos
              </button>
            </div>

            {dataError && (
              <div
                className="rounded-xl border px-4 py-3 text-sm text-amber-100"
                style={{
                  background: "rgba(120, 53, 15, 0.35)",
                  borderColor: "rgba(251, 191, 36, 0.35)",
                }}
              >
                {dataError}
              </div>
            )}

            <div className="flex flex-wrap gap-2 border-b border-slate-700/80 pb-3">
              {(
                [
                  ["portes", "Portes"],
                  ["facturas", "Facturas"],
                  ["clientes", "Clientes"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => {
                    setTab(id);
                    setFilterText("");
                  }}
                  className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                    tab === id
                      ? "bg-blue-600 text-white"
                      : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <label className="block">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Filtrar tabla
              </span>
              <input
                type="search"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Buscar en columnas visibles…"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
              />
            </label>

            <p className="text-xs text-slate-500">
              {tabLoading
                ? "Cargando datos…"
                : `${currentFiltered.length} fila(s) · se exporta lo mostrado tras el filtro.`}
            </p>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                disabled={exportDisabled}
                onClick={() => void handleExportExcel()}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5"
              >
                {exportBusy === "excel" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FileSpreadsheet className="w-4 h-4" />
                )}
                Exportar Excel
              </button>
              <button
                type="button"
                disabled={exportDisabled}
                onClick={() => void handleExportPdf()}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/90 hover:bg-slate-700 disabled:opacity-50 text-slate-100 text-sm font-semibold px-4 py-2.5"
              >
                {exportBusy === "pdf" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4" />
                )}
                Exportar PDF
              </button>
            </div>

            <div className="rounded-xl border border-slate-700/60 overflow-hidden">
              <div className="max-h-64 overflow-auto">
                {tab === "portes" && (
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="sticky top-0 bg-slate-900/95 text-slate-400 uppercase tracking-wide">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Fecha</th>
                        <th className="px-3 py-2 font-semibold">Origen</th>
                        <th className="px-3 py-2 font-semibold">Destino</th>
                        <th className="px-3 py-2 font-semibold">Estado</th>
                        <th className="px-3 py-2 font-semibold text-right">Precio</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {loadPortes ? (
                        <tr>
                          <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                            Cargando…
                          </td>
                        </tr>
                      ) : filteredPortes.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                            No hay portes que coincidan.
                          </td>
                        </tr>
                      ) : (
                        filteredPortes.slice(0, 80).map((p) => (
                          <tr key={p.id} className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 whitespace-nowrap">{p.fecha}</td>
                            <td className="px-3 py-2 max-w-[140px] truncate" title={p.origen}>
                              {p.origen}
                            </td>
                            <td className="px-3 py-2 max-w-[140px] truncate" title={p.destino}>
                              {p.destino}
                            </td>
                            <td className="px-3 py-2">{p.estado}</td>
                            <td className="px-3 py-2 text-right font-mono">
                              {Number(p.precio_pactado ?? 0).toLocaleString("es-ES", {
                                style: "currency",
                                currency: "EUR",
                              })}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
                {tab === "facturas" && (
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="sticky top-0 bg-slate-900/95 text-slate-400 uppercase tracking-wide">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Número</th>
                        <th className="px-3 py-2 font-semibold">Fecha</th>
                        <th className="px-3 py-2 font-semibold">Total</th>
                        <th className="px-3 py-2 font-semibold">Cliente</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {loadFacturas ? (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-slate-500">
                            Cargando…
                          </td>
                        </tr>
                      ) : filteredFacturas.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-slate-500">
                            No hay facturas que coincidan.
                          </td>
                        </tr>
                      ) : (
                        filteredFacturas.slice(0, 80).map((f) => (
                          <tr key={String(f.id)} className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 font-medium">{f.numero_factura ?? "—"}</td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {f.fecha_emision ? String(f.fecha_emision).slice(0, 10) : "—"}
                            </td>
                            <td className="px-3 py-2">
                              {Number(f.total_factura ?? 0).toLocaleString("es-ES", {
                                style: "currency",
                                currency: "EUR",
                              })}
                            </td>
                            <td className="px-3 py-2 max-w-[180px] truncate">
                              {f.cliente_nombre ?? "—"}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
                {tab === "clientes" && (
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="sticky top-0 bg-slate-900/95 text-slate-400 uppercase tracking-wide">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Nombre</th>
                        <th className="px-3 py-2 font-semibold">NIF</th>
                        <th className="px-3 py-2 font-semibold">ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {loadClientes ? (
                        <tr>
                          <td colSpan={3} className="px-3 py-6 text-center text-slate-500">
                            Cargando…
                          </td>
                        </tr>
                      ) : filteredClientes.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="px-3 py-6 text-center text-slate-500">
                            No hay clientes que coincidan.
                          </td>
                        </tr>
                      ) : (
                        filteredClientes.slice(0, 80).map((c) => (
                          <tr key={c.id} className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 font-medium">{c.nombre}</td>
                            <td className="px-3 py-2">{c.nif ?? "—"}</td>
                            <td className="px-3 py-2 font-mono text-[0.65rem] break-all">{c.id}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
              </div>
              {((tab === "portes" && filteredPortes.length > 80) ||
                (tab === "facturas" && filteredFacturas.length > 80) ||
                (tab === "clientes" && filteredClientes.length > 80)) && (
                <p className="text-[0.65rem] text-slate-500 px-3 py-2 border-t border-slate-800">
                  Vista previa limitada a 80 filas; la exportación incluye todas las filas filtradas.
                </p>
              )}
            </div>
          </div>
        </main>
      </RoleGuard>
    </AppShell>
  );
}
