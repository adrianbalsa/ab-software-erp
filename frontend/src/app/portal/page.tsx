"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, FileText, LogOut, Package, Receipt } from "lucide-react";

import {
  API_BASE,
  authHeaders,
  fetchPortalFacturas,
  fetchPortalPortes,
  jwtRbacRole,
  notifyJwtUpdated,
  parseApiError,
  type AppRbacRole,
  type PortalFacturaRow,
  type PortalPorteRow,
  portalAlbaranPdfUrl,
  portalFacturaPdfUrl,
  postPortalSetupMandate,
  refreshAccessToken,
} from "@/lib/api";
import { SetupMandateCard } from "@/components/portal/SetupMandateCard";
import { clearAuthToken, getAuthToken } from "@/lib/auth";

type Tab = "entregas" | "facturas";

async function downloadAuthedPdf(url: string, filename: string) {
  async function doFetch(): Promise<Response> {
    return fetch(url, { credentials: "include", headers: { ...authHeaders() } });
  }
  let res = await doFetch();
  if (res.status === 401) {
    const t = await refreshAccessToken();
    if (t) res = await doFetch();
  }
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const blob = await res.blob();
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(u);
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    return d.toLocaleString("es-ES", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fmtMoney(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function PortalClientePage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("entregas");
  const [portes, setPortes] = useState<PortalPorteRow[]>([]);
  const [facturas, setFacturas] = useState<PortalFacturaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [role, setRole] = useState<AppRbacRole | null>(null);
  const [isSettingUpMandate, setIsSettingUpMandate] = useState(false);
  const [hasActiveMandate, setHasActiveMandate] = useState(false);

  const allowed = role === "cliente";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, f] = await Promise.all([fetchPortalPortes(), fetchPortalFacturas()]);
      setPortes(p);
      setFacturas(f);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar datos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setRole(jwtRbacRole());
  }, []);

  useEffect(() => {
    if (role === null) return;
    try {
      const t = getAuthToken();
      if (!t) {
        router.replace(`/login?redirect=${encodeURIComponent("/portal")}`);
        return;
      }
    } catch {
      router.replace("/login");
      return;
    }
    if (role !== "cliente") {
      router.replace("/dashboard");
      return;
    }
    void load();
  }, [role, load, router]);

  const logout = () => {
    try {
      clearAuthToken();
      notifyJwtUpdated();
    } catch {
      /* ignore */
    }
    router.replace("/login");
  };

  const handleSetupMandate = useCallback(async () => {
    if (isSettingUpMandate) return;
    setIsSettingUpMandate(true);
    setError(null);
    try {
      const out = await postPortalSetupMandate();
      if (out.has_active_mandate) {
        setHasActiveMandate(true);
      }
      if (!out.redirect_url || !out.redirect_url.trim()) {
        throw new Error("No se recibió URL de redirección para GoCardless.");
      }
      window.location.href = out.redirect_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo iniciar la domiciliación.");
      setIsSettingUpMandate(false);
    }
  }, [isSettingUpMandate]);

  if (role === null || !allowed) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-sm text-zinc-500">
        {role === null ? "Cargando…" : "Redirigiendo…"}
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 pb-12 pt-8 sm:px-6">
      <header className="mb-8 flex flex-col gap-4 border-b border-zinc-200/90 pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-zinc-900 text-white shadow-sm">
            <Building2 className="h-6 w-6" aria-hidden />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Ventanilla externa
            </p>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-900">
              AB Logistics OS
            </h1>
            <p className="mt-0.5 text-sm text-zinc-600">
              Entregas y documentación fiscal
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden text-xs text-zinc-500 sm:inline">
            Sesión segura · {API_BASE.replace(/^https?:\/\//, "")}
          </span>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm transition hover:bg-zinc-50"
          >
            <LogOut className="h-4 w-4" />
            Salir
          </button>
        </div>
      </header>

      <div className="mb-6 flex gap-1 rounded-xl border border-zinc-200/90 bg-white p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setTab("entregas")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
            tab === "entregas"
              ? "bg-zinc-900 text-white shadow"
              : "text-zinc-600 hover:bg-zinc-50"
          }`}
        >
          <Package className="h-4 w-4" />
          Últimas entregas
        </button>
        <button
          type="button"
          onClick={() => setTab("facturas")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
            tab === "facturas"
              ? "bg-zinc-900 text-white shadow"
              : "text-zinc-600 hover:bg-zinc-50"
          }`}
        >
          <Receipt className="h-4 w-4" />
          Mis facturas
        </button>
      </div>

      {error && (
        <div
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          role="alert"
        >
          {error}
        </div>
      )}

      {tab === "entregas" && (
        <section className="rounded-2xl border border-zinc-200/90 bg-white shadow-sm">
          <div className="border-b border-zinc-100 px-5 py-4">
            <h2 className="text-base font-semibold text-zinc-900">Últimas entregas</h2>
            <p className="text-sm text-zinc-500">
              Albaranes con prueba de entrega (POD) disponibles para descarga.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/80 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  <th className="px-5 py-3">Origen</th>
                  <th className="px-5 py-3">Destino</th>
                  <th className="px-5 py-3">Fecha de entrega</th>
                  <th className="px-5 py-3 text-right">Documento</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-zinc-500">
                      Cargando…
                    </td>
                  </tr>
                ) : portes.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-zinc-500">
                      No hay entregas firmadas todavía.
                    </td>
                  </tr>
                ) : (
                  portes.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-zinc-50 last:border-0 hover:bg-zinc-50/50"
                    >
                      <td className="px-5 py-3.5 font-medium text-zinc-800">{row.origen}</td>
                      <td className="px-5 py-3.5 text-zinc-700">{row.destino}</td>
                      <td className="px-5 py-3.5 text-zinc-600">{fmtDate(row.fecha_entrega)}</td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          type="button"
                          disabled={downloading === `p-${row.id}`}
                          onClick={async () => {
                            setDownloading(`p-${row.id}`);
                            try {
                              await downloadAuthedPdf(
                                portalAlbaranPdfUrl(row.id),
                                `albaran-${row.id}.pdf`,
                              );
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "Error al descargar");
                            } finally {
                              setDownloading(null);
                            }
                          }}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600/30 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-900 transition hover:bg-emerald-100 disabled:opacity-60"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {downloading === `p-${row.id}` ? "Descargando…" : "Descargar albarán firmado"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "facturas" && (
        <section className="rounded-2xl border border-zinc-200/90 bg-white shadow-sm">
          <div className="px-5 pt-5">
            <SetupMandateCard
              hasActiveMandate={hasActiveMandate}
              isLoading={isSettingUpMandate}
              onSetup={handleSetupMandate}
            />
          </div>
          <div className="border-b border-zinc-100 px-5 py-4">
            <h2 className="text-base font-semibold text-zinc-900">Mis facturas</h2>
            <p className="text-sm text-zinc-500">
              Facturas emitidas a su cuenta y estado de cobro.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-100 bg-zinc-50/80 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  <th className="px-5 py-3">Número</th>
                  <th className="px-5 py-3">Fecha</th>
                  <th className="px-5 py-3">Importe</th>
                  <th className="px-5 py-3">Estado</th>
                  <th className="px-5 py-3 text-right">PDF</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-zinc-500">
                      Cargando…
                    </td>
                  </tr>
                ) : facturas.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-zinc-500">
                      No hay facturas emitidas aún.
                    </td>
                  </tr>
                ) : (
                  facturas.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-zinc-50 last:border-0 hover:bg-zinc-50/50"
                    >
                      <td className="px-5 py-3.5 font-mono text-sm font-medium text-zinc-900">
                        {row.numero_factura}
                      </td>
                      <td className="px-5 py-3.5 text-zinc-600">
                        {row.fecha_emision?.slice(0, 10) ?? "—"}
                      </td>
                      <td className="px-5 py-3.5 text-zinc-800">{fmtMoney(row.total_factura)}</td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                            row.estado_pago === "Pagada"
                              ? "bg-emerald-100 text-emerald-900"
                              : "bg-amber-100 text-amber-900"
                          }`}
                        >
                          {row.estado_pago}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          type="button"
                          disabled={downloading === `f-${row.id}`}
                          onClick={async () => {
                            setDownloading(`f-${row.id}`);
                            try {
                              await downloadAuthedPdf(
                                portalFacturaPdfUrl(row.id),
                                `factura-${row.id}.pdf`,
                              );
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "Error al descargar");
                            } finally {
                              setDownloading(null);
                            }
                          }}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-800 shadow-sm transition hover:bg-zinc-50 disabled:opacity-60"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {downloading === `f-${row.id}` ? "Descargando…" : "Descargar factura"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <p className="mt-8 text-center text-xs text-zinc-500">
        ¿Operaciones internas?{" "}
        <Link href="/dashboard" className="font-medium text-zinc-700 underline-offset-2 hover:underline">
          Ir al panel de gestión
        </Link>
      </p>
    </div>
  );
}
