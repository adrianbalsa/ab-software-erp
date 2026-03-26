"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Car,
  CreditCard,
  FileText,
  FileSearch,
  GitCompare,
  LayoutDashboard,
  Leaf,
  Link2,
  MapPin,
  Menu,
  Package,
  Receipt,
  Settings,
  Shield,
  Truck,
  Users,
  Wallet,
  FileDown,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { QuotaStatusCard } from "@/components/QuotaStatusCard";
import { useRole } from "@/hooks/useRole";
import type { AppRbacRole } from "@/lib/api";

const navLink =
  "flex items-center px-3 py-2.5 rounded-lg transition-colors text-sm font-medium";
const navInactive = "hover:bg-slate-800/80 hover:text-white text-slate-300";
const navActive = "bg-[#2563eb]/15 text-[#60a5fa] border border-[#2563eb]/25";

const sidebarBg = {
  background: "linear-gradient(180deg, #0b1224 0%, #060a14 100%)",
} as const;

type Props = {
  children: ReactNode;
  active?:
    | "dashboard"
    | "finanzas"
    | "conciliacion"
    | "tesoreria"
    | "exportar"
    | "portes"
    | "sostenibilidad"
    | "facturas"
    | "gastos"
    | "admin"
    | "seguridad"
    | "flota"
    | "operaciones"
    | "clientes"
    | "integrations"
    | "auditoria";
};

function showNavItem(
  key:
    | "finanzas"
    | "facturas"
    | "gastos"
    | "flota"
    | "sostenibilidad"
    | "admin"
    | "clientes",
  role: AppRbacRole,
): boolean {
  if (key === "clientes") {
    return role === "owner";
  }
  if (role === "owner") return true;
  if (role === "traffic_manager") {
    return key === "flota" || key === "sostenibilidad";
  }
  return false;
}

function ShellNavAndFooter({
  active,
  role,
  onNavLinkClick,
}: {
  active: Props["active"];
  role: AppRbacRole;
  onNavLinkClick?: () => void;
}) {
  const p = onNavLinkClick ? { onClick: onNavLinkClick } : {};

  return (
    <>
      <nav className="flex-1 overflow-y-auto px-4 py-6 space-y-1 min-h-0">
        <Link
          id="tour-nav-dashboard"
          href="/dashboard"
          className={`${navLink} ${active === "dashboard" ? navActive : navInactive}`}
          {...p}
        >
          <LayoutDashboard className="w-5 h-5 mr-3 shrink-0" />
          Dashboard
        </Link>
        {showNavItem("clientes", role) && (
          <Link
            id="tour-nav-clientes"
            href="/clientes"
            className={`nav-clientes ${navLink} ${active === "clientes" ? navActive : navInactive}`}
            {...p}
          >
            <Users className="w-5 h-5 mr-3 shrink-0" />
            Clientes
          </Link>
        )}
        {showNavItem("finanzas", role) && (
          <>
            <Link
              href="/finanzas"
              className={`${navLink} ${active === "finanzas" ? navActive : navInactive}`}
              {...p}
            >
              <FileText className="w-5 h-5 mr-3 shrink-0" />
              Finanzas
            </Link>
            <Link
              href="/finanzas/conciliacion"
              className={`${navLink} ${active === "conciliacion" ? navActive : navInactive}`}
              {...p}
            >
              <GitCompare className="w-5 h-5 mr-3 shrink-0" />
              Conciliación IA
            </Link>
            {role === "owner" && (
              <Link
                id="tour-nav-finanzas"
                href="/dashboard/finanzas/tesoreria"
                className={`nav-finanzas ${navLink} ${active === "tesoreria" ? navActive : navInactive}`}
                {...p}
              >
                <Wallet className="w-5 h-5 mr-3 shrink-0" />
                Tesorería y Riesgos
              </Link>
            )}
            <Link
              href="/finanzas/exportar"
              className={`${navLink} ${active === "exportar" ? navActive : navInactive}`}
              {...p}
            >
              <FileDown className="w-5 h-5 mr-3 shrink-0" />
              Exportar
            </Link>
            {role === "owner" && (
              <Link
                href="/dashboard/finanzas/auditoria"
                className={`${navLink} ${active === "auditoria" ? navActive : navInactive}`}
                {...p}
              >
                <FileSearch className="w-5 h-5 mr-3 shrink-0" />
                Auditoría Fiscal
              </Link>
            )}
          </>
        )}
        <Link
          id="tour-nav-portes"
          href="/portes"
          className={`nav-portes ${navLink} ${active === "portes" ? navActive : navInactive}`}
          {...p}
        >
          <Truck className="w-5 h-5 mr-3 shrink-0" />
          Portes
        </Link>
        {showNavItem("flota", role) && (
          <>
            <Link
              id="tour-nav-flota"
              href="/flota"
              className={`nav-flota ${navLink} ${active === "flota" ? navActive : navInactive}`}
              {...p}
            >
              <Car className="w-5 h-5 mr-3 shrink-0" />
              Flota
            </Link>
            <Link
              href="/operaciones/live"
              className={`${navLink} ${active === "operaciones" ? navActive : navInactive}`}
              {...p}
            >
              <MapPin className="w-5 h-5 mr-3 shrink-0" />
              Centro de mando
            </Link>
          </>
        )}
        {showNavItem("sostenibilidad", role) && (
          <Link
            href="/sostenibilidad"
            className={`${navLink} ${active === "sostenibilidad" ? navActive : navInactive}`}
            {...p}
          >
            <Package className="w-5 h-5 mr-3 shrink-0" />
            Sostenibilidad
          </Link>
        )}
        {showNavItem("facturas", role) && (
          <Link
            href="/facturas"
            className={`${navLink} ${active === "facturas" ? navActive : navInactive}`}
            {...p}
          >
            <Receipt className="w-5 h-5 mr-3 shrink-0" />
            Facturas
          </Link>
        )}
        {showNavItem("gastos", role) && (
          <Link
            href="/gastos"
            className={`${navLink} ${active === "gastos" ? navActive : navInactive}`}
            {...p}
          >
            <CreditCard className="w-5 h-5 mr-3 shrink-0" />
            Gastos
          </Link>
        )}
        {showNavItem("admin", role) && (
          <Link
            href="/admin"
            className={`${navLink} ${active === "admin" ? navActive : navInactive}`}
            {...p}
          >
            <Settings className="w-5 h-5 mr-3 shrink-0" />
            Admin
          </Link>
        )}
        {role === "owner" && (
          <Link
            href="/settings/integrations"
            className={`${navLink} ${active === "integrations" ? navActive : navInactive}`}
            {...p}
          >
            <Link2 className="w-5 h-5 mr-3 shrink-0" />
            Integraciones
          </Link>
        )}
        <Link
          href="/perfil/seguridad"
          className={`${navLink} ${active === "seguridad" ? navActive : navInactive}`}
          {...p}
        >
          <Shield className="w-5 h-5 mr-3 shrink-0" />
          Seguridad
        </Link>
      </nav>
      <div className="px-4 pb-3 shrink-0">
        <QuotaStatusCard />
      </div>
      <div className="p-4 border-t border-slate-800/80 text-xs text-slate-500 flex items-center gap-2 shrink-0">
        <Leaf className="w-4 h-4 text-emerald-500" />
        <span>AB Logistics OS</span>
      </div>
    </>
  );
}

export function AppShell({ children, active }: Props) {
  const pathname = usePathname();
  const { role } = useRole();
  const [mobileOpen, setMobileOpen] = useState(false);

  const resolvedActive: Props["active"] = (() => {
    if (active) return active;
    if (pathname === "/dashboard/finanzas/tesoreria") return "tesoreria";
    if (pathname === "/dashboard/finanzas/auditoria") return "auditoria";
    if (pathname === "/finanzas/conciliacion") return "conciliacion";
    if (pathname === "/finanzas/exportar") return "exportar";
    if (pathname === "/finanzas" || pathname.startsWith("/finanzas/")) return "finanzas";
    if (pathname === "/dashboard" || pathname.startsWith("/dashboard")) return "dashboard";
    if (pathname.startsWith("/portes")) return "portes";
    if (pathname.startsWith("/flota")) return "flota";
    if (pathname.startsWith("/operaciones")) return "operaciones";
    if (pathname.startsWith("/clientes")) return "clientes";
    if (pathname.startsWith("/facturas")) return "facturas";
    if (pathname.startsWith("/gastos")) return "gastos";
    if (pathname.startsWith("/sostenibilidad")) return "sostenibilidad";
    if (pathname.startsWith("/admin")) return "admin";
    if (pathname.startsWith("/settings/integrations")) return "integrations";
    if (pathname.startsWith("/perfil/seguridad")) return "seguridad";
    return "dashboard";
  })();

  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [mobileOpen]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const onBp = () => {
      if (mq.matches) setMobileOpen(false);
    };
    mq.addEventListener("change", onBp);
    return () => mq.removeEventListener("change", onBp);
  }, []);

  const closeMobile = () => setMobileOpen(false);

  return (
    <div className="flex min-h-screen ab-app-gradient font-sans text-slate-800 overflow-x-hidden">
      <aside
        className="hidden lg:flex w-64 shrink-0 flex-col border-r border-slate-800/80 text-slate-300"
        style={sidebarBg}
      >
        <div className="h-16 flex items-center px-6 border-b border-slate-800/80 shrink-0">
          <Truck className="w-6 h-6 text-[#60a5fa] mr-2 shrink-0" />
          <span className="text-white font-bold text-lg tracking-tight">
            AB Logistics OS
          </span>
        </div>
        <ShellNavAndFooter active={resolvedActive} role={role} />
      </aside>

      {mobileOpen ? (
        <>
          <button
            type="button"
            className="lg:hidden fixed inset-0 z-[60] bg-black/60"
            aria-label="Cerrar menú"
            onClick={closeMobile}
          />
          <aside
            className="lg:hidden fixed inset-y-0 left-0 z-[70] flex w-[min(100%,18rem)] flex-col border-r border-slate-800/80 text-slate-300 shadow-2xl"
            style={sidebarBg}
          >
            <div className="h-16 flex items-center justify-between gap-2 px-4 border-b border-slate-800/80 shrink-0">
              <div className="flex min-w-0 items-center">
                <Truck className="w-6 h-6 text-[#60a5fa] mr-2 shrink-0" />
                <span className="text-white font-bold text-sm tracking-tight truncate">
                  AB Logistics OS
                </span>
              </div>
              <button
                type="button"
                onClick={closeMobile}
                className="shrink-0 rounded-lg p-2 text-slate-400 hover:bg-slate-800/80 hover:text-white"
                aria-label="Cerrar menú"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <ShellNavAndFooter
              active={resolvedActive}
              role={role}
              onNavLinkClick={closeMobile}
            />
          </aside>
        </>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div
          className="lg:hidden sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-slate-800/80 px-4 text-slate-200"
          style={sidebarBg}
        >
          <button
            type="button"
            className="rounded-lg p-2 hover:bg-slate-800/80"
            aria-label="Abrir menú de navegación"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <span className="font-bold tracking-tight truncate">AB Logistics OS</span>
        </div>
        {children}
      </div>
    </div>
  );
}
