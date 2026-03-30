"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Building2,
  ClipboardList,
  LayoutDashboard,
  LineChart,
  Shield,
  Truck,
  Users,
} from "lucide-react";
import {
  createAdminEmpresa,
  fetchAdminAuditoria,
  fetchAdminEmpresas,
  fetchAdminMetricasFacturacion,
  fetchAdminUsuarios,
  patchAdminEmpresa,
  patchAdminUsuario,
} from "@/lib/admin-api";
import type { AuditoriaAdminRow, EmpresaCreateBody, MetricasSaaSFacturacionOut, UsuarioAdminOut } from "@/types/admin";
import type { EmpresaOut } from "@/types/empresa";
import { getAuthToken } from "@/lib/auth";

const PLANS = ["starter", "professional", "business", "enterprise"] as const;
const ROLES = ["user", "manager", "admin", "empleado", "gestor"] as const;

type TabId = "empresas" | "usuarios" | "metricas" | "auditoria" | "facturacion";

function formatEUR(n: number) {
  return n.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export default function AdminPage() {
  const [tab, setTab] = useState<TabId>("empresas");
  const [token, setToken] = useState<string | null>(null);
  const [empresas, setEmpresas] = useState<EmpresaOut[]>([]);
  const [usuarios, setUsuarios] = useState<UsuarioAdminOut[]>([]);
  const [auditoria, setAuditoria] = useState<AuditoriaAdminRow[]>([]);
  const [metricas, setMetricas] = useState<MetricasSaaSFacturacionOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<EmpresaCreateBody>({
    nif: "",
    nombre_legal: "",
    nombre_comercial: "",
    plan: "starter",
    email: "",
    telefono: "",
    direccion: "",
    activa: true,
  });

  const [selEmpresaId, setSelEmpresaId] = useState<string>("");
  const [selPlan, setSelPlan] = useState<string>("starter");
  const [selActiva, setSelActiva] = useState(true);

  const [selUsuarioId, setSelUsuarioId] = useState<string>("");
  const [selRol, setSelRol] = useState<string>("user");
  const [selUsuarioActivo, setSelUsuarioActivo] = useState(true);

  const [audLimit, setAudLimit] = useState(100);
  const [filtroAccion, setFiltroAccion] = useState("");
  const [filtroTabla, setFiltroTabla] = useState("");

  useEffect(() => {
    try {
      setToken(getAuthToken());
    } catch {
      setToken(null);
    }
  }, []);

  const loadEmpresas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEmpresas(await fetchAdminEmpresas());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadUsuarios = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsuarios(await fetchAdminUsuarios());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAuditoria = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAuditoria(await fetchAdminAuditoria(audLimit));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [audLimit]);

  const loadMetricas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMetricas(await fetchAdminMetricasFacturacion());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    if (tab === "empresas") void loadEmpresas();
    if (tab === "usuarios") {
      void loadUsuarios();
      void loadEmpresas(); // mapa nombre empresa_id → label
    }
    if (tab === "auditoria") void loadAuditoria();
    if (tab === "metricas") void loadMetricas();
  }, [token, tab, loadEmpresas, loadUsuarios, loadAuditoria, loadMetricas]);

  const empresaSeleccionada = useMemo(
    () => empresas.find((e) => e.id === selEmpresaId),
    [empresas, selEmpresaId]
  );

  const usuarioSeleccionado = useMemo(
    () => usuarios.find((u) => u.id === selUsuarioId),
    [usuarios, selUsuarioId]
  );

  useEffect(() => {
    if (empresaSeleccionada) {
      setSelPlan(empresaSeleccionada.plan);
      setSelActiva(empresaSeleccionada.activa);
    }
  }, [empresaSeleccionada]);

  useEffect(() => {
    if (usuarioSeleccionado) {
      setSelRol(usuarioSeleccionado.rol);
      setSelUsuarioActivo(usuarioSeleccionado.activo);
    }
  }, [usuarioSeleccionado]);

  useEffect(() => {
    if (empresas.length && !selEmpresaId) setSelEmpresaId(empresas[0].id);
  }, [empresas, selEmpresaId]);

  useEffect(() => {
    if (usuarios.length && !selUsuarioId) setSelUsuarioId(usuarios[0].id);
  }, [usuarios, selUsuarioId]);

  const mapaEmpresaNombre = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of empresas) {
      m.set(e.id, e.nombre_comercial?.trim() || e.nombre_legal || e.id);
    }
    return m;
  }, [empresas]);

  const auditoriaFiltrada = useMemo(() => {
    return auditoria.filter((r) => {
      const a = (r.accion || "").toUpperCase();
      const t = (r.tabla || "").toLowerCase();
      if (filtroAccion && !a.includes(filtroAccion.toUpperCase())) return false;
      if (filtroTabla && !t.includes(filtroTabla.toLowerCase())) return false;
      return true;
    });
  }, [auditoria, filtroAccion, filtroTabla]);

  const onCreateEmpresa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const body: EmpresaCreateBody = {
        nif: createForm.nif.trim().toUpperCase(),
        nombre_legal: createForm.nombre_legal.trim(),
        nombre_comercial:
          (createForm.nombre_comercial || "").trim() || createForm.nombre_legal.trim(),
        plan: createForm.plan || "starter",
        email: createForm.email?.trim() || null,
        telefono: createForm.telefono?.trim() || null,
        direccion: createForm.direccion?.trim() || null,
        activa: true,
      };
      await createAdminEmpresa(body);
      setCreateForm({
        nif: "",
        nombre_legal: "",
        nombre_comercial: "",
        plan: "starter",
        email: "",
        telefono: "",
        direccion: "",
        activa: true,
      });
      await loadEmpresas();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    }
  };

  const onSaveEmpresa = async () => {
    if (!selEmpresaId) return;
    setError(null);
    try {
      await patchAdminEmpresa(selEmpresaId, { plan: selPlan, activa: selActiva });
      await loadEmpresas();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    }
  };

  const onSaveUsuario = async () => {
    if (!selUsuarioId) return;
    setError(null);
    try {
      await patchAdminUsuario(selUsuarioId, { rol: selRol, activo: selUsuarioActivo });
      await loadUsuarios();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error");
    }
  };

  const exportAudCsv = () => {
    const headers = ["id", "accion", "tabla", "registro_id", "empresa_id", "fecha", "timestamp"];
    const lines = [
      headers.join(";"),
      ...auditoriaFiltrada.map((r) =>
        headers
          .map((h) => {
            const v = (r as Record<string, unknown>)[h];
            if (v == null) return "";
            const s = typeof v === "object" ? JSON.stringify(v) : String(v);
            return `"${s.replace(/"/g, '""')}"`;
          })
          .join(";")
      ),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `auditoria_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!token) {
    return (
      <div className="min-h-screen ab-app-gradient flex items-center justify-center p-6">
        <div className="ab-glass max-w-md w-full rounded-2xl p-8 text-center space-y-4">
          <Shield className="w-12 h-12 text-[var(--ab-primary)] mx-auto" />
          <h1 className="text-xl font-bold text-slate-900">Panel de administración</h1>
          <p className="text-sm text-slate-600">
            Inicia sesión en la aplicación y vuelve aquí con un usuario <strong>rol admin</strong>.
          </p>
          <Link
            href="/portes"
            className="inline-block text-sm font-semibold text-[var(--ab-primary)] hover:underline"
          >
            Ir a login (Portes)
          </Link>
        </div>
      </div>
    );
  }

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: "empresas", label: "Empresas", icon: <Building2 className="w-4 h-4" /> },
    { id: "usuarios", label: "Usuarios", icon: <Users className="w-4 h-4" /> },
    { id: "metricas", label: "Métricas SaaS", icon: <LineChart className="w-4 h-4" /> },
    { id: "auditoria", label: "Auditoría", icon: <ClipboardList className="w-4 h-4" /> },
    { id: "facturacion", label: "Facturación", icon: <Shield className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen ab-app-gradient flex font-sans text-slate-800">
      <aside className="w-64 shrink-0 ab-sidebar text-slate-300 flex flex-col border-r border-slate-800/80">
        <div className="h-16 flex items-center px-5 border-b border-slate-800/80">
          <Truck className="w-6 h-6 text-[var(--ab-accent)] mr-2" />
          <div>
            <span className="text-white font-bold text-sm tracking-tight block">AB Logistics</span>
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Admin Console</span>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm hover:bg-slate-800/80 transition-colors"
          >
            <LayoutDashboard className="w-4 h-4" />
            Dashboard
          </Link>
          <Link
            href="/portes"
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm hover:bg-slate-800/80 transition-colors"
          >
            <Truck className="w-4 h-4" />
            Portes
          </Link>
          <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm bg-[var(--ab-primary)]/15 text-[var(--ab-accent)] border border-[var(--ab-primary)]/30">
            <Shield className="w-4 h-4" />
            Administración
          </div>
        </nav>
      </aside>

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-16 ab-header border-b border-slate-200/80 flex items-center justify-between px-8">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Panel de administración</h1>
            <p className="text-xs text-slate-500">Gestión global — equivalente al módulo Streamlit legacy</p>
          </div>
        </header>

        <div className="px-8 pt-4 border-b border-slate-200/60 bg-white/40">
          <div className="flex gap-1 overflow-x-auto pb-0">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg border-b-2 transition-colors whitespace-nowrap ${
                  tab === t.id
                    ? "border-[var(--ab-primary)] text-[var(--ab-primary)] bg-white shadow-sm"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 p-8 overflow-auto">
          {error && (
            <div className="mb-6 ab-alert-error rounded-xl px-4 py-3 text-sm">{error}</div>
          )}

          {tab === "empresas" && (
            <div className="space-y-8 max-w-6xl">
              <section className="ab-card rounded-2xl p-6">
                <h2 className="text-lg font-bold text-slate-900 mb-4">Empresas registradas</h2>
                {loading && empresas.length === 0 ? (
                  <p className="text-slate-500 text-sm">Cargando…</p>
                ) : empresas.length === 0 ? (
                  <p className="text-slate-500 text-sm">No hay empresas.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-200/80">
                    <table className="ab-table w-full text-sm">
                      <thead>
                        <tr>
                          <th>Nombre comercial</th>
                          <th>NIF</th>
                          <th>Plan</th>
                          <th>Activa</th>
                          <th>Alta</th>
                        </tr>
                      </thead>
                      <tbody>
                        {empresas.map((e) => (
                          <tr key={e.id}>
                            <td className="font-medium text-slate-900">
                              {e.nombre_comercial || e.nombre_legal}
                            </td>
                            <td className="font-mono text-xs">{e.nif}</td>
                            <td>
                              <span className="ab-badge">{e.plan}</span>
                            </td>
                            <td>{e.activa ? "Sí" : "No"}</td>
                            <td className="text-slate-500">{e.fecha_registro ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="ab-card rounded-2xl p-6">
                <h2 className="text-lg font-bold text-slate-900 mb-4">Crear empresa</h2>
                <form onSubmit={onCreateEmpresa} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <input
                    className="ab-input"
                    placeholder="NIF/CIF *"
                    maxLength={12}
                    value={createForm.nif}
                    onChange={(ev) => setCreateForm({ ...createForm, nif: ev.target.value })}
                    required
                  />
                  <input
                    className="ab-input"
                    placeholder="Razón social (nombre_legal) *"
                    value={createForm.nombre_legal}
                    onChange={(ev) => setCreateForm({ ...createForm, nombre_legal: ev.target.value })}
                    required
                  />
                  <input
                    className="ab-input"
                    placeholder="Nombre comercial"
                    value={createForm.nombre_comercial || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, nombre_comercial: ev.target.value })}
                  />
                  <select
                    className="ab-input"
                    value={createForm.plan}
                    onChange={(ev) => setCreateForm({ ...createForm, plan: ev.target.value })}
                  >
                    {PLANS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                  <input
                    className="ab-input"
                    placeholder="Email"
                    type="email"
                    value={createForm.email || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, email: ev.target.value })}
                  />
                  <input
                    className="ab-input"
                    placeholder="Teléfono"
                    value={createForm.telefono || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, telefono: ev.target.value })}
                  />
                  <input
                    className="ab-input md:col-span-2"
                    placeholder="Dirección"
                    value={createForm.direccion || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, direccion: ev.target.value })}
                  />
                  <button type="submit" className="ab-btn-primary md:col-span-2">
                    Crear empresa
                  </button>
                </form>
              </section>

              {empresas.length > 0 && (
                <section className="ab-card rounded-2xl p-6">
                  <h2 className="text-lg font-bold text-slate-900 mb-4">Plan y estado</h2>
                  <div className="flex flex-wrap gap-4 items-end">
                    <div className="min-w-[200px] flex-1">
                      <label className="ab-label">Empresa</label>
                      <select
                        className="ab-input w-full"
                        value={selEmpresaId}
                        onChange={(ev) => setSelEmpresaId(ev.target.value)}
                      >
                        {empresas.map((e) => (
                          <option key={e.id} value={e.id}>
                            {(e.nombre_comercial || e.nombre_legal) + ` (${e.nif})`}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="min-w-[160px]">
                      <label className="ab-label">Plan</label>
                      <select className="ab-input w-full" value={selPlan} onChange={(ev) => setSelPlan(ev.target.value)}>
                        {PLANS.map((p) => (
                          <option key={p} value={p}>
                            {p}
                          </option>
                        ))}
                      </select>
                    </div>
                    <label className="flex items-center gap-2 text-sm pb-2">
                      <input type="checkbox" checked={selActiva} onChange={(ev) => setSelActiva(ev.target.checked)} />
                      Empresa activa
                    </label>
                    <button type="button" onClick={() => void onSaveEmpresa()} className="ab-btn-primary">
                      Guardar
                    </button>
                  </div>
                </section>
              )}
            </div>
          )}

          {tab === "usuarios" && (
            <div className="space-y-8 max-w-6xl">
              <section className="ab-card rounded-2xl p-6">
                <h2 className="text-lg font-bold text-slate-900 mb-4">Usuarios</h2>
                {loading && usuarios.length === 0 ? (
                  <p className="text-slate-500 text-sm">Cargando…</p>
                ) : usuarios.length === 0 ? (
                  <p className="text-slate-500 text-sm">No hay usuarios.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-200/80">
                    <table className="ab-table w-full text-sm">
                      <thead>
                        <tr>
                          <th>Usuario</th>
                          <th>Email</th>
                          <th>Rol</th>
                          <th>Activo</th>
                          <th>Empresa</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usuarios.map((u) => (
                          <tr key={u.id}>
                            <td className="font-medium">{u.username}</td>
                            <td>{u.email ?? "—"}</td>
                            <td>
                              <span className="ab-badge">{u.rol}</span>
                            </td>
                            <td>{u.activo ? "Sí" : "No"}</td>
                            <td className="text-slate-600">{mapaEmpresaNombre.get(u.empresa_id) ?? u.empresa_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {usuarios.length > 0 && (
                <section className="ab-card rounded-2xl p-6">
                  <h2 className="text-lg font-bold text-slate-900 mb-4">Editar usuario</h2>
                  <div className="flex flex-wrap gap-4 items-end">
                    <div className="min-w-[240px] flex-1">
                      <label className="ab-label">Usuario</label>
                      <select
                        className="ab-input w-full"
                        value={selUsuarioId}
                        onChange={(ev) => setSelUsuarioId(ev.target.value)}
                      >
                        {usuarios.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.username} {u.email ? `(${u.email})` : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="min-w-[140px]">
                      <label className="ab-label">Rol</label>
                      <select className="ab-input w-full" value={selRol} onChange={(ev) => setSelRol(ev.target.value)}>
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </div>
                    <label className="flex items-center gap-2 text-sm pb-2">
                      <input
                        type="checkbox"
                        checked={selUsuarioActivo}
                        onChange={(ev) => setSelUsuarioActivo(ev.target.checked)}
                      />
                      Activo
                    </label>
                    <button type="button" onClick={() => void onSaveUsuario()} className="ab-btn-primary">
                      Guardar usuario
                    </button>
                  </div>
                </section>
              )}
            </div>
          )}

          {tab === "metricas" && (
            <div className="max-w-5xl space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="ab-kpi">
                  <p className="ab-kpi-label">Ingresos brutos</p>
                  <p className="ab-kpi-value">{metricas ? formatEUR(metricas.total_bruto) : "—"}</p>
                </div>
                <div className="ab-kpi">
                  <p className="ab-kpi-label">IVA</p>
                  <p className="ab-kpi-value">{metricas ? formatEUR(metricas.total_iva) : "—"}</p>
                </div>
                <div className="ab-kpi ab-kpi-accent">
                  <p className="ab-kpi-label">Ingreso neto</p>
                  <p className="ab-kpi-value">{metricas ? formatEUR(metricas.ingreso_neto) : "—"}</p>
                </div>
                <div className="ab-kpi">
                  <p className="ab-kpi-label">Facturas / ARPU</p>
                  <p className="ab-kpi-value text-lg">
                    {metricas ? `${metricas.n_facturas} · ${formatEUR(metricas.arpu)}` : "—"}
                  </p>
                </div>
              </div>
              <p className="text-xs text-slate-500">
                Agregado global de tabla <code className="bg-slate-100 px-1 rounded">facturas</code> (panel SaaS).
              </p>
            </div>
          )}

          {tab === "auditoria" && (
            <div className="space-y-4 max-w-6xl">
              <div className="flex flex-wrap gap-3 items-end">
                <div>
                  <label className="ab-label">Acción contiene</label>
                  <input
                    className="ab-input"
                    value={filtroAccion}
                    onChange={(ev) => setFiltroAccion(ev.target.value)}
                    placeholder="GENERAR_FACTURA"
                  />
                </div>
                <div>
                  <label className="ab-label">Tabla contiene</label>
                  <input
                    className="ab-input"
                    value={filtroTabla}
                    onChange={(ev) => setFiltroTabla(ev.target.value)}
                    placeholder="facturas"
                  />
                </div>
                <div>
                  <label className="ab-label">Límite</label>
                  <select
                    className="ab-input"
                    value={audLimit}
                    onChange={(ev) => setAudLimit(Number(ev.target.value))}
                  >
                    {[50, 100, 200, 500].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>
                <button type="button" className="ab-btn-secondary" onClick={() => void loadAuditoria()}>
                  Recargar
                </button>
                <button type="button" className="ab-btn-primary" onClick={exportAudCsv}>
                  Exportar CSV
                </button>
              </div>
              <div className="ab-card rounded-2xl overflow-hidden p-0">
                <div className="overflow-x-auto">
                  <table className="ab-table w-full text-xs">
                    <thead>
                      <tr>
                        <th>Acción</th>
                        <th>Tabla</th>
                        <th>Registro</th>
                        <th>Empresa</th>
                        <th>Fecha</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditoriaFiltrada.map((r, i) => (
                        <tr key={r.id || i}>
                          <td className="font-mono">{r.accion}</td>
                          <td>{r.tabla}</td>
                          <td className="max-w-[120px] truncate">{r.registro_id}</td>
                          <td className="truncate max-w-[100px]">{r.empresa_id}</td>
                          <td className="text-slate-500 whitespace-nowrap">
                            {r.timestamp || r.fecha || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {tab === "facturacion" && (
            <div className="ab-card rounded-2xl p-8 max-w-xl space-y-4">
              <h2 className="text-lg font-bold text-slate-900">Facturación</h2>
              <p className="text-sm text-slate-600">
                La emisión legal de facturas de transporte está en{" "}
                <Link href="/portes" className="text-[var(--ab-primary)] font-medium hover:underline">
                  Portes
                </Link>{" "}
                (VeriFactu + PDF). Las facturas SaaS globales se integran aquí cuando conectes el
                proveedor de pagos.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
