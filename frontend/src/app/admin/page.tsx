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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const PLANS = ["starter", "professional", "business", "enterprise"] as const;
const ROLES = ["user", "manager", "admin", "empleado", "gestor"] as const;

/** Bento / terminal-style containers (admin dashboard) */
const BENTO =
  "rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-6 backdrop-blur-md shadow-2xl transition-all";

const inputAdminClass =
  "h-10 border-zinc-800 bg-zinc-900/50 text-zinc-100 placeholder:text-zinc-500 focus-visible:border-zinc-600 focus-visible:ring-zinc-600/30 md:text-sm";

const btnPrimaryClass = "bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:ring-emerald-500/40";

const tableShell = "overflow-x-auto rounded-xl border border-zinc-800/60";
const tableClass = "w-full text-sm text-zinc-300";
const tableHead =
  "border-b border-zinc-800 bg-zinc-950/80 text-left text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500";
const tableCell = "border-b border-zinc-800/40 px-4 py-3";

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

  useEffect(() => {
    if (!error) return;
    toast.error(error, { id: "admin-api-error" });
  }, [error]);

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
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-6">
        <div
          className={cn(
            BENTO,
            "max-w-md w-full space-y-4 text-center"
          )}
        >
          <Shield className="mx-auto h-12 w-12 text-emerald-500/90" />
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Panel de administración</h1>
          <p className="text-sm text-zinc-400">
            Inicia sesión en la aplicación y vuelve aquí con un usuario <strong className="text-zinc-200">rol admin</strong>.
          </p>
          <Link
            href="/portes"
            className="inline-block text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
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
    <div className="flex min-h-screen bg-zinc-950 font-sans text-zinc-100">
      <aside className="m-4 flex w-[15.5rem] shrink-0 flex-col rounded-2xl border border-zinc-800/50 bg-black shadow-2xl backdrop-blur-md">
        <div className="flex h-16 items-center border-b border-zinc-800/50 px-5">
          <Truck className="mr-2 h-6 w-6 text-emerald-500/90" />
          <div>
            <span className="block text-sm font-semibold tracking-tight text-zinc-100">AB Logistics</span>
            <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-500">Admin Console</span>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-900/80 hover:text-zinc-100"
          >
            <LayoutDashboard className="h-4 w-4" />
            Dashboard
          </Link>
          <Link
            href="/portes"
            className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-900/80 hover:text-zinc-100"
          >
            <Truck className="h-4 w-4" />
            Portes
          </Link>
          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-2.5 text-sm font-medium text-emerald-300">
            <Shield className="h-4 w-4" />
            Administración
          </div>
        </nav>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col pr-4 pt-4 pb-4">
        <header className="flex h-16 shrink-0 items-center justify-between rounded-xl border border-zinc-800/50 bg-zinc-900/30 px-8 backdrop-blur-md">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Panel de administración</h1>
            <p className="text-xs text-zinc-400">Gestión global — equivalente al módulo Streamlit legacy</p>
          </div>
        </header>

        <div className="mt-4 rounded-xl border border-zinc-800/50 bg-zinc-900/20 px-4 pt-2 backdrop-blur-sm">
          <div className="flex gap-1 overflow-x-auto pb-0">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex items-center gap-2 whitespace-nowrap rounded-t-lg border-b-2 px-4 py-3 text-sm font-medium transition-colors",
                  tab === t.id
                    ? "border-emerald-500 text-emerald-400"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                )}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-auto py-6 pr-2">
          {tab === "empresas" && (
            <div className="grid max-w-6xl grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={cn(BENTO, "lg:col-span-2")}>
                <h2 className="mb-1 text-lg font-semibold tracking-tight text-zinc-100">Empresas registradas</h2>
                <p className="mb-4 text-sm text-zinc-400">Listado de empresas dadas de alta en la plataforma.</p>
                {loading && empresas.length === 0 ? (
                  <p className="text-sm text-zinc-400">Cargando…</p>
                ) : empresas.length === 0 ? (
                  <p className="text-sm text-zinc-400">No hay empresas.</p>
                ) : (
                  <div className={tableShell}>
                    <table className={tableClass}>
                      <thead>
                        <tr>
                          <th className={tableHead}>Nombre comercial</th>
                          <th className={tableHead}>NIF</th>
                          <th className={tableHead}>Plan</th>
                          <th className={tableHead}>Activa</th>
                          <th className={tableHead}>Alta</th>
                        </tr>
                      </thead>
                      <tbody>
                        {empresas.map((e) => (
                          <tr key={e.id} className="hover:bg-zinc-800/30">
                            <td className={cn(tableCell, "font-medium text-zinc-100")}>
                              {e.nombre_comercial || e.nombre_legal}
                            </td>
                            <td className={cn(tableCell, "font-mono text-xs text-zinc-400")}>{e.nif}</td>
                            <td className={tableCell}>
                              <span className="inline-flex rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300">
                                {e.plan}
                              </span>
                            </td>
                            <td className={tableCell}>{e.activa ? "Sí" : "No"}</td>
                            <td className={cn(tableCell, "text-zinc-500")}>{e.fecha_registro ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className={BENTO}>
                <h2 className="mb-1 text-lg font-semibold tracking-tight text-zinc-100">Crear empresa</h2>
                <p className="mb-4 text-sm text-zinc-400">Alta de nueva empresa en el sistema.</p>
                <form onSubmit={onCreateEmpresa} className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Input
                    className={inputAdminClass}
                    placeholder="NIF/CIF *"
                    maxLength={12}
                    value={createForm.nif}
                    onChange={(ev) => setCreateForm({ ...createForm, nif: ev.target.value })}
                    required
                  />
                  <Input
                    className={inputAdminClass}
                    placeholder="Razón social (nombre_legal) *"
                    value={createForm.nombre_legal}
                    onChange={(ev) => setCreateForm({ ...createForm, nombre_legal: ev.target.value })}
                    required
                  />
                  <Input
                    className={inputAdminClass}
                    placeholder="Nombre comercial"
                    value={createForm.nombre_comercial || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, nombre_comercial: ev.target.value })}
                  />
                  <select
                    className={cn(inputAdminClass, "rounded-lg px-3")}
                    value={createForm.plan}
                    onChange={(ev) => setCreateForm({ ...createForm, plan: ev.target.value })}
                  >
                    {PLANS.map((p) => (
                      <option key={p} value={p} className="bg-zinc-900">
                        {p}
                      </option>
                    ))}
                  </select>
                  <Input
                    className={inputAdminClass}
                    placeholder="Email"
                    type="email"
                    value={createForm.email || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, email: ev.target.value })}
                  />
                  <Input
                    className={inputAdminClass}
                    placeholder="Teléfono"
                    value={createForm.telefono || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, telefono: ev.target.value })}
                  />
                  <Input
                    className={cn(inputAdminClass, "md:col-span-2")}
                    placeholder="Dirección"
                    value={createForm.direccion || ""}
                    onChange={(ev) => setCreateForm({ ...createForm, direccion: ev.target.value })}
                  />
                  <Button type="submit" className={cn(btnPrimaryClass, "md:col-span-2 h-10 w-full")}>
                    Crear empresa
                  </Button>
                </form>
              </section>

              {empresas.length > 0 && (
                <section className={cn(BENTO, "lg:col-span-2")}>
                  <h2 className="mb-1 text-lg font-semibold tracking-tight text-zinc-100">Plan y estado</h2>
                  <p className="mb-4 text-sm text-zinc-400">Actualiza plan y visibilidad de la empresa seleccionada.</p>
                  <div className="flex flex-wrap items-end gap-4">
                    <div className="min-w-[200px] flex-1">
                      <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                        Empresa
                      </label>
                      <select
                        className={cn(inputAdminClass, "w-full rounded-lg px-3")}
                        value={selEmpresaId}
                        onChange={(ev) => setSelEmpresaId(ev.target.value)}
                      >
                        {empresas.map((e) => (
                          <option key={e.id} value={e.id} className="bg-zinc-900">
                            {(e.nombre_comercial || e.nombre_legal) + ` (${e.nif})`}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="min-w-[160px]">
                      <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                        Plan
                      </label>
                      <select
                        className={cn(inputAdminClass, "w-full rounded-lg px-3")}
                        value={selPlan}
                        onChange={(ev) => setSelPlan(ev.target.value)}
                      >
                        {PLANS.map((p) => (
                          <option key={p} value={p} className="bg-zinc-900">
                            {p}
                          </option>
                        ))}
                      </select>
                    </div>
                    <label className="flex items-center gap-2 pb-2 text-sm text-zinc-300">
                      <input
                        type="checkbox"
                        className="rounded border-zinc-600 bg-zinc-900"
                        checked={selActiva}
                        onChange={(ev) => setSelActiva(ev.target.checked)}
                      />
                      Empresa activa
                    </label>
                    <Button type="button" onClick={() => void onSaveEmpresa()} className={cn(btnPrimaryClass, "h-10")}>
                      Guardar
                    </Button>
                  </div>
                </section>
              )}
            </div>
          )}

          {tab === "usuarios" && (
            <div className="grid max-w-6xl grid-cols-1 gap-6 lg:grid-cols-2">
              <section className={cn(BENTO, "lg:col-span-2")}>
                <h2 className="mb-1 text-lg font-semibold tracking-tight text-zinc-100">Usuarios</h2>
                <p className="mb-4 text-sm text-zinc-400">Usuarios registrados y su asignación por empresa.</p>
                {loading && usuarios.length === 0 ? (
                  <p className="text-sm text-zinc-400">Cargando…</p>
                ) : usuarios.length === 0 ? (
                  <p className="text-sm text-zinc-400">No hay usuarios.</p>
                ) : (
                  <div className={tableShell}>
                    <table className={tableClass}>
                      <thead>
                        <tr>
                          <th className={tableHead}>Usuario</th>
                          <th className={tableHead}>Email</th>
                          <th className={tableHead}>Rol</th>
                          <th className={tableHead}>Activo</th>
                          <th className={tableHead}>Empresa</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usuarios.map((u) => (
                          <tr key={u.id} className="hover:bg-zinc-800/30">
                            <td className={cn(tableCell, "font-medium text-zinc-100")}>{u.username}</td>
                            <td className={tableCell}>{u.email ?? "—"}</td>
                            <td className={tableCell}>
                              <span className="inline-flex rounded-full bg-indigo-500/15 px-2 py-0.5 text-xs font-medium text-indigo-300">
                                {u.rol}
                              </span>
                            </td>
                            <td className={tableCell}>{u.activo ? "Sí" : "No"}</td>
                            <td className={cn(tableCell, "text-zinc-400")}>
                              {mapaEmpresaNombre.get(u.empresa_id) ?? u.empresa_id}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {usuarios.length > 0 && (
                <section className={cn(BENTO, "lg:col-span-2")}>
                  <h2 className="mb-1 text-lg font-semibold tracking-tight text-zinc-100">Editar usuario</h2>
                  <p className="mb-4 text-sm text-zinc-400">Rol y estado del usuario seleccionado.</p>
                  <div className="flex flex-wrap items-end gap-4">
                    <div className="min-w-[240px] flex-1">
                      <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                        Usuario
                      </label>
                      <select
                        className={cn(inputAdminClass, "w-full rounded-lg px-3")}
                        value={selUsuarioId}
                        onChange={(ev) => setSelUsuarioId(ev.target.value)}
                      >
                        {usuarios.map((u) => (
                          <option key={u.id} value={u.id} className="bg-zinc-900">
                            {u.username} {u.email ? `(${u.email})` : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="min-w-[140px]">
                      <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                        Rol
                      </label>
                      <select
                        className={cn(inputAdminClass, "w-full rounded-lg px-3")}
                        value={selRol}
                        onChange={(ev) => setSelRol(ev.target.value)}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r} className="bg-zinc-900">
                            {r}
                          </option>
                        ))}
                      </select>
                    </div>
                    <label className="flex items-center gap-2 pb-2 text-sm text-zinc-300">
                      <input
                        type="checkbox"
                        className="rounded border-zinc-600 bg-zinc-900"
                        checked={selUsuarioActivo}
                        onChange={(ev) => setSelUsuarioActivo(ev.target.checked)}
                      />
                      Activo
                    </label>
                    <Button type="button" onClick={() => void onSaveUsuario()} className={cn(btnPrimaryClass, "h-10")}>
                      Guardar usuario
                    </Button>
                  </div>
                </section>
              )}
            </div>
          )}

          {tab === "metricas" && (
            <div className="max-w-5xl space-y-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className={BENTO}>
                  <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">Ingresos brutos</p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
                    {metricas ? formatEUR(metricas.total_bruto) : "—"}
                  </p>
                </div>
                <div className={BENTO}>
                  <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">IVA</p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
                    {metricas ? formatEUR(metricas.total_iva) : "—"}
                  </p>
                </div>
                <div className={cn(BENTO, "border-emerald-500/30 bg-emerald-950/20")}>
                  <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-400">Ingreso neto</p>
                  <p className="mt-2 text-2xl font-semibold tracking-tight text-emerald-300">
                    {metricas ? formatEUR(metricas.ingreso_neto) : "—"}
                  </p>
                </div>
                <div className={BENTO}>
                  <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">Facturas / ARPU</p>
                  <p className="mt-2 text-lg font-semibold tracking-tight text-zinc-100">
                    {metricas ? `${metricas.n_facturas} · ${formatEUR(metricas.arpu)}` : "—"}
                  </p>
                </div>
              </div>
              <p className="text-xs text-zinc-500">
                Agregado global de tabla{" "}
                <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-zinc-300">facturas</code> (panel SaaS).
              </p>
            </div>
          )}

          {tab === "auditoria" && (
            <div className="max-w-6xl space-y-4">
              <div className={cn(BENTO, "flex flex-wrap items-end gap-3 py-5")}>
                <div>
                  <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                    Acción contiene
                  </label>
                  <Input
                    className={cn(inputAdminClass, "w-[220px]")}
                    value={filtroAccion}
                    onChange={(ev) => setFiltroAccion(ev.target.value)}
                    placeholder="GENERAR_FACTURA"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                    Tabla contiene
                  </label>
                  <Input
                    className={cn(inputAdminClass, "w-[180px]")}
                    value={filtroTabla}
                    onChange={(ev) => setFiltroTabla(ev.target.value)}
                    placeholder="facturas"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-[0.65rem] font-semibold uppercase tracking-wider text-zinc-500">
                    Límite
                  </label>
                  <select
                    className={cn(inputAdminClass, "w-[100px] rounded-lg px-3")}
                    value={audLimit}
                    onChange={(ev) => setAudLimit(Number(ev.target.value))}
                  >
                    {[50, 100, 200, 500].map((n) => (
                      <option key={n} value={n} className="bg-zinc-900">
                        {n}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 border-zinc-700 bg-zinc-900/50 text-zinc-200 hover:bg-zinc-800"
                  onClick={() => void loadAuditoria()}
                >
                  Recargar
                </Button>
                <Button type="button" className={cn(btnPrimaryClass, "h-10")} onClick={exportAudCsv}>
                  Exportar CSV
                </Button>
              </div>
              <div className={cn(BENTO, "overflow-hidden p-0")}>
                <div className="overflow-x-auto">
                  <table className={cn(tableClass, "text-xs")}>
                    <thead>
                      <tr>
                        <th className={tableHead}>Acción</th>
                        <th className={tableHead}>Tabla</th>
                        <th className={tableHead}>Registro</th>
                        <th className={tableHead}>Empresa</th>
                        <th className={tableHead}>Fecha</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditoriaFiltrada.map((r, i) => (
                        <tr key={r.id || i} className="hover:bg-zinc-800/30">
                          <td className={cn(tableCell, "font-mono text-zinc-300")}>{r.accion}</td>
                          <td className={tableCell}>{r.tabla}</td>
                          <td className={cn(tableCell, "max-w-[120px] truncate")}>{r.registro_id}</td>
                          <td className={cn(tableCell, "max-w-[100px] truncate")}>{r.empresa_id}</td>
                          <td className={cn(tableCell, "whitespace-nowrap text-zinc-500")}>
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
            <div className={cn(BENTO, "max-w-xl space-y-2")}>
              <h2 className="text-lg font-semibold tracking-tight text-zinc-100">Facturación</h2>
              <p className="text-sm leading-relaxed text-zinc-400">
                La emisión legal de facturas de transporte está en{" "}
                <Link href="/portes" className="font-medium text-emerald-400 hover:text-emerald-300 hover:underline">
                  Portes
                </Link>{" "}
                (VeriFactu + PDF). Las facturas SaaS globales se integran aquí cuando conectes el proveedor de pagos.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
