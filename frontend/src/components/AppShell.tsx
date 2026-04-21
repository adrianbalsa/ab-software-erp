"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Activity,
  BadgeCheck,
  BadgeEuro,
  BarChart3,
  Car,
  CreditCard,
  FileDown,
  FileSearch,
  GitCompare,
  LayoutDashboard,
  Landmark,
  Leaf,
  LifeBuoy,
  LineChart,
  Link2,
  Target,
  Map as MapIcon,
  MapPin,
  Menu,
  Receipt,
  Settings,
  Shield,
  Truck,
  Users,
  Wallet,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useEffect, useState } from "react";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { ConfiguracionNavSection, SidebarUserSection } from "@/components/layout/Sidebar";
import { sidebarNavIcon, sidebarNavRow } from "@/components/layout/sidebarNavStyles";
import { QuotaStatusCard } from "@/components/QuotaStatusCard";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { useRole } from "@/hooks/useRole";
import { isOwnerLike, isTrafficManager, type AppRbacRole } from "@/lib/api";
import { cn } from "@/lib/utils";

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
    | "eficiencia"
    | "operaciones"
    | "clientes"
    | "integrations"
    | "auditoria"
    | "certificaciones"
    | "desarrolladores"
    | "analitica"
    | "bi"
    | "vampire_radar"
    | "simulador"
    | "mapa"
    | "billing";
};

function NavSectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="px-3 pb-2 pt-1">
      <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{title}</p>
      <p className="mt-0.5 text-[10px] font-medium normal-case tracking-normal text-zinc-600">
        {subtitle}
      </p>
    </div>
  );
}

function BrandLogo({ className = "h-8 w-8 md:h-10 md:w-10" }: { className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt="AB Logistics logo"
      width={40}
      height={40}
      className={cn("shrink-0 object-contain", className)}
      priority
    />
  );
}

function SidebarNavLink({
  href,
  active,
  icon: Icon,
  title,
  subtitle,
  id,
  className,
  ...rest
}: {
  href: string;
  active: boolean;
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  id?: string;
  className?: string;
} & Omit<ComponentProps<typeof Link>, "href" | "className" | "children">) {
  return (
    <Link
      id={id}
      href={href}
      className={cn(sidebarNavRow(active), className)}
      {...rest}
    >
      <Icon className={sidebarNavIcon(active)} aria-hidden />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="leading-snug">{title}</span>
        {subtitle ? (
          <span className="text-[11px] font-normal leading-snug text-zinc-500 group-hover:text-zinc-400">
            {subtitle}
          </span>
        ) : null}
      </span>
    </Link>
  );
}

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
  // Solo owner / admin y developer pueden ver clientes
  if (key === "clientes") {
    return isOwnerLike(role) || role === "developer";
  }

  // Solo owner / admin y developer pueden ver finanzas y admin (roles ADMIN/SUPERADMIN)
  // Los roles traffic_manager, driver, cliente son equivalentes a STAFF
  if (key === "finanzas" || key === "admin") {
    return isOwnerLike(role) || role === "developer";
  }

  // Owner / admin puede ver todo
  if (isOwnerLike(role)) return true;
  
  // Developer puede ver casi todo excepto operaciones de flota (driver-specific)
  if (role === "developer") {
    return key !== "flota" && key !== "sostenibilidad";
  }
  
  // Traffic manager (STAFF operativo) puede ver flota y sostenibilidad (sin módulos fiscal-búnker)
  if (role === "traffic_manager") {
    return key === "flota" || key === "sostenibilidad";
  }
  
  // Driver y cliente: acceso muy limitado
  return false;
}

function ShellNavAndFooter({
  active,
  onNavLinkClick,
}: {
  active: Props["active"];
  onNavLinkClick?: () => void;
}) {
  const { role } = useRole();
  const { catalog } = useOptionalLocaleCatalog();
  const s = catalog.appShell;
  const hideFinanceBunkerAndAdminNav = isTrafficManager(role);
  const p = onNavLinkClick ? { onClick: onNavLinkClick } : {};
  const L = s.links;

  return (
    <>
      <nav className="flex min-h-0 flex-1 flex-col gap-0 overflow-y-auto px-4 py-6" aria-label={s.navAriaLabel}>
        {/* INSTITUCIONAL */}
        <section className="mt-0">
          <NavSectionHeader title={s.sections.institutional.title} subtitle={s.sections.institutional.subtitle} />
          <div className="flex flex-col gap-0.5">
            <SidebarNavLink
              id="tour-nav-dashboard"
              href="/dashboard"
              active={active === "dashboard"}
              icon={LayoutDashboard}
              title={L.dashboard[0]}
              subtitle={L.dashboard[1]}
              {...p}
            />
            {isOwnerLike(role) && (
              <SidebarNavLink
                href="/dashboard/analitica"
                active={active === "analitica"}
                icon={BarChart3}
                title={L.matrizCip[0]}
                subtitle={L.matrizCip[1]}
                {...p}
              />
            )}
            {isOwnerLike(role) && (
              <SidebarNavLink
                href="/dashboard/bi"
                active={active === "bi"}
                icon={Target}
                title={L.bi[0]}
                subtitle={L.bi[1]}
                {...p}
              />
            )}
            {isOwnerLike(role) && (
              <SidebarNavLink
                href="/dashboard/vampire-radar"
                active={active === "vampire_radar"}
                icon={Activity}
                title={L.vampire[0]}
                subtitle={L.vampire[1]}
                {...p}
              />
            )}
            {showNavItem("flota", role) && (
              <SidebarNavLink
                href="/operaciones/live"
                active={active === "operaciones"}
                icon={MapPin}
                title={L.command[0]}
                subtitle={L.command[1]}
                {...p}
              />
            )}
          </div>
        </section>

        {/* OPERACIONES */}
        <section className="mt-6">
          <NavSectionHeader title={s.sections.operations.title} subtitle={s.sections.operations.subtitle} />
          <div className="flex flex-col gap-0.5">
            <SidebarNavLink
              id="tour-nav-portes"
              href="/portes"
              active={active === "portes"}
              icon={Truck}
              title={L.portes[0]}
              subtitle={L.portes[1]}
              className="nav-portes"
              {...p}
            />
            {showNavItem("flota", role) && (
              <>
                <SidebarNavLink
                  id="tour-nav-flota"
                  href="/flota"
                  active={active === "flota"}
                  icon={Car}
                  title={L.flota[0]}
                  subtitle={L.flota[1]}
                  className="nav-flota"
                  {...p}
                />
                <SidebarNavLink
                  href="/flota/eficiencia"
                  active={active === "eficiencia"}
                  icon={Activity}
                  title={L.eficiencia[0]}
                  subtitle={L.eficiencia[1]}
                  className="nav-flota-eficiencia"
                  {...p}
                />
                {!hideFinanceBunkerAndAdminNav ? (
                  <SidebarNavLink
                    href="/dashboard/mapa"
                    active={active === "mapa"}
                    icon={MapIcon}
                    title={L.mapa[0]}
                    subtitle={L.mapa[1]}
                    {...p}
                  />
                ) : null}
              </>
            )}
            {showNavItem("sostenibilidad", role) && (
              <SidebarNavLink
                href="/sostenibilidad"
                active={active === "sostenibilidad"}
                icon={Leaf}
                title={L.sostenibilidad[0]}
                subtitle={L.sostenibilidad[1]}
                {...p}
              />
            )}
          </div>
        </section>

        {/* FINANZAS & FISCAL (Búnker) — oculto explícitamente para traffic_manager */}
        {!hideFinanceBunkerAndAdminNav && showNavItem("finanzas", role) && (
          <section className="mt-6">
            <NavSectionHeader title={s.sections.finance.title} subtitle={s.sections.finance.subtitle} />
            <div className="flex flex-col gap-0.5">
              <SidebarNavLink
                href="/finanzas"
                active={active === "finanzas"}
                icon={Wallet}
                title={L.finanzas[0]}
                subtitle={L.finanzas[1]}
                {...p}
              />
              {showNavItem("facturas", role) && (
                <SidebarNavLink
                  href="/facturas"
                  active={active === "facturas"}
                  icon={Receipt}
                  title={L.facturacion[0]}
                  subtitle={L.facturacion[1]}
                  {...p}
                />
              )}
              {showNavItem("gastos", role) && (
                <SidebarNavLink
                  href="/gastos"
                  active={active === "gastos"}
                  icon={CreditCard}
                  title={L.gastos[0]}
                  subtitle={L.gastos[1]}
                  {...p}
                />
              )}
              <SidebarNavLink
                href="/finanzas/conciliacion"
                active={active === "conciliacion"}
                icon={GitCompare}
                title={L.conciliacion[0]}
                subtitle={L.conciliacion[1]}
                {...p}
              />
              {isOwnerLike(role) && (
                <SidebarNavLink
                  id="tour-nav-finanzas"
                  href="/dashboard/finanzas/tesoreria"
                  active={active === "tesoreria"}
                  icon={Landmark}
                  title={L.tesoreria[0]}
                  subtitle={L.tesoreria[1]}
                  className="nav-finanzas"
                  {...p}
                />
              )}
              {isOwnerLike(role) && (
                <SidebarNavLink
                  href="/dashboard/finanzas/auditoria"
                  active={active === "auditoria"}
                  icon={FileSearch}
                  title={L.auditoria[0]}
                  subtitle={L.auditoria[1]}
                  {...p}
                />
              )}
              {isOwnerLike(role) && (
                <SidebarNavLink
                  href="/dashboard/certificaciones"
                  active={active === "certificaciones"}
                  icon={BadgeCheck}
                  title={L.certificaciones[0]}
                  subtitle={L.certificaciones[1]}
                  {...p}
                />
              )}
            </div>
          </section>
        )}

        {/* GESTIÓN */}
        {(showNavItem("clientes", role) || isOwnerLike(role)) && (
          <section className="mt-6">
            <NavSectionHeader title={s.sections.management.title} subtitle={s.sections.management.subtitle} />
            <div className="flex flex-col gap-0.5">
              {showNavItem("clientes", role) && (
                <SidebarNavLink
                  id="tour-nav-clientes"
                  href="/clientes"
                  active={active === "clientes"}
                  icon={Users}
                  title={L.clientes[0]}
                  subtitle={L.clientes[1]}
                  className="nav-clientes"
                  {...p}
                />
              )}
              {isOwnerLike(role) && (
                <SidebarNavLink
                  href="/dashboard/finanzas/simulador"
                  active={active === "simulador"}
                  icon={LineChart}
                  title={L.simulador[0]}
                  subtitle={L.simulador[1]}
                  {...p}
                />
              )}
            </div>
          </section>
        )}

        {/* SISTEMA */}
        <section className="mt-6">
          <NavSectionHeader title={s.sections.system.title} subtitle={s.sections.system.subtitle} />
          <div className="flex flex-col gap-0.5">
            <SidebarNavLink
              href="/#help"
              active={false}
              icon={LifeBuoy}
              title={catalog.nav.help}
              subtitle={catalog.nav.helpSub}
              {...p}
            />
            {isOwnerLike(role) && (
              <SidebarNavLink
                href="/dashboard/settings/billing"
                active={active === "billing"}
                icon={BadgeEuro}
                title={catalog.nav.billing}
                subtitle={catalog.nav.billingSub}
                {...p}
              />
            )}
            {!hideFinanceBunkerAndAdminNav && showNavItem("admin", role) && (
              <SidebarNavLink
                href="/admin"
                active={active === "admin"}
                icon={Settings}
                title={L.configuracion[0]}
                subtitle={L.configuracion[1]}
                {...p}
              />
            )}
            {isOwnerLike(role) && (
              <SidebarNavLink
                href="/settings/integrations"
                active={active === "integrations"}
                icon={Link2}
                title={L.integraciones[0]}
                subtitle={L.integraciones[1]}
                {...p}
              />
            )}
            {!hideFinanceBunkerAndAdminNav ? (
              <ConfiguracionNavSection active={active} role={role} onNavLinkClick={onNavLinkClick} />
            ) : null}
            <SidebarNavLink
              href="/perfil/seguridad"
              active={active === "seguridad"}
              icon={Shield}
              title={L.seguridad[0]}
              subtitle={L.seguridad[1]}
              {...p}
            />
            {!hideFinanceBunkerAndAdminNav && showNavItem("finanzas", role) && (
              <SidebarNavLink
                href="/finanzas/exportar"
                active={active === "exportar"}
                icon={FileDown}
                title={L.exportar[0]}
                subtitle={L.exportar[1]}
                {...p}
              />
            )}
          </div>
        </section>
      </nav>
      <div className="shrink-0 px-4 pb-3">
        <QuotaStatusCard />
      </div>
      <SidebarUserSection />
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-t border-zinc-800/80 p-4 text-xs text-zinc-500">
        <div className="flex items-center gap-2">
          <Leaf className="h-4 w-4 text-emerald-500" aria-hidden />
          <span>{s.sidebarBrand}</span>
        </div>
        <LocaleSwitcher />
      </div>
    </>
  );
}

export function AppShell({ children, active }: Props) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { catalog } = useOptionalLocaleCatalog();
  const s = catalog.appShell;

  const resolvedActive: Props["active"] = (() => {
    if (active) return active;
    if (pathname.startsWith("/dashboard/configuracion")) return "desarrolladores";
    if (pathname === "/dashboard/analitica") return "analitica";
    if (pathname === "/dashboard/bi" || pathname.startsWith("/dashboard/bi/")) return "bi";
    if (pathname === "/dashboard/vampire-radar" || pathname.startsWith("/dashboard/vampire-radar/")) {
      return "vampire_radar";
    }
    if (pathname.startsWith("/dashboard/settings/billing")) return "billing";
    if (pathname === "/dashboard/finanzas/tesoreria") return "tesoreria";
    if (pathname === "/dashboard/finanzas/simulador") return "simulador";
    if (pathname === "/dashboard/finanzas/auditoria") return "auditoria";
    if (pathname === "/dashboard/certificaciones") return "certificaciones";
    if (pathname.startsWith("/dashboard/portes")) return "portes";
    if (pathname === "/finanzas/conciliacion") return "conciliacion";
    if (pathname === "/finanzas/exportar") return "exportar";
    if (pathname === "/finanzas" || pathname.startsWith("/finanzas/")) return "finanzas";
    if (pathname === "/dashboard" || pathname.startsWith("/dashboard")) return "dashboard";
    if (pathname.startsWith("/portes")) return "portes";
    if (pathname.startsWith("/flota/eficiencia")) return "eficiencia";
    if (pathname === "/dashboard/mapa" || pathname.startsWith("/dashboard/mapa/")) return "mapa";
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
    <div className="flex min-h-screen bg-zinc-950 font-sans text-zinc-100 overflow-x-hidden">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950 text-zinc-300 lg:flex">
        <div className="flex h-16 shrink-0 items-center border-b border-zinc-800 px-6">
          <BrandLogo className="mr-2 h-8 w-8" />
          <span className="text-white font-bold text-lg tracking-tight">{s.sidebarBrand}</span>
        </div>
        <ShellNavAndFooter active={resolvedActive} />
      </aside>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent
          side="left"
          className="border-zinc-800 bg-zinc-950 text-zinc-300"
          aria-label={s.mainNavSheetAria}
        >
          <div className="flex h-16 shrink-0 items-center justify-between gap-2 border-b border-zinc-800 px-4">
            <div className="flex min-w-0 items-center">
              <BrandLogo className="mr-2 h-8 w-8" />
              <SheetTitle className="truncate border-0 p-0 text-sm font-bold text-white">{s.sidebarBrand}</SheetTitle>
            </div>
            <button
              type="button"
              onClick={closeMobile}
              className="shrink-0 rounded-lg p-2 text-zinc-400 transition-all duration-200 hover:bg-zinc-900/80 hover:text-white"
              aria-label={s.closeMenu}
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <ShellNavAndFooter active={resolvedActive} onNavLinkClick={closeMobile} />
        </SheetContent>
      </Sheet>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-x-hidden px-3 pb-4 pt-0 sm:px-4 lg:px-0 lg:pb-0">
          <div
          className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-zinc-800 bg-zinc-950 px-2 text-zinc-200 sm:px-3 lg:hidden"
        >
          <button
            type="button"
            className="rounded-lg p-2 transition-all duration-200 hover:bg-zinc-900/80"
            aria-label={s.openMenu}
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <BrandLogo className="h-8 w-8" />
          <span className="truncate font-bold tracking-tight">{s.sidebarBrand}</span>
        </div>
        <div className="min-h-0 min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
