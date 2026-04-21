"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Leaf, LogOut, Moon, Package, Receipt, Sun } from "lucide-react";

import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { PortalClienteRiskModal } from "@/components/portal-cliente/PortalClienteRiskModal";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { PortalClienteOnboardingProvider } from "@/context/PortalClienteOnboardingContext";
import { API_BASE, jwtRbacRole, notifyJwtUpdated } from "@/lib/api";
import { clearAuthToken, getAuthToken } from "@/lib/auth";
import { isPortalApiBaseDebugVisible, portalSupportMailto } from "@/lib/portalShellEnv";
import { cn } from "@/lib/utils";

export function PortalClienteAppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { catalog } = useOptionalLocaleCatalog();
  const p = catalog.portalCliente;
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return true;
    try {
      return localStorage.getItem("abl-portal-theme") !== "light";
    } catch {
      return true;
    }
  });

  const nav = useMemo(
    () =>
      [
        { href: "/portal-cliente/mis-portes" as const, label: p.navShipments, icon: Package },
        { href: "/portal-cliente/facturas" as const, label: p.navInvoices, icon: Receipt },
        { href: "/portal-cliente/sostenibilidad" as const, label: p.navEsg, icon: Leaf },
        { href: "/portal-cliente/analytics" as const, label: p.navBi, icon: BarChart3 },
      ] as const,
    [p.navShipments, p.navInvoices, p.navEsg, p.navBi],
  );

  const footerLinks = useMemo(
    () =>
      [
        { href: "/help", label: p.footer.help },
        { href: "/privacidad", label: p.footer.privacy },
        { href: "/legal", label: p.footer.legal },
      ] as const,
    [p.footer.help, p.footer.privacy, p.footer.legal],
  );

  const showApiDebug = isPortalApiBaseDebugVisible();
  const apiHostShort = API_BASE.replace(/^https?:\/\//, "");

  useEffect(() => {
    try {
      localStorage.setItem("abl-portal-theme", dark ? "dark" : "light");
    } catch {
      /* ignore */
    }
  }, [dark]);

  useEffect(() => {
    const role = jwtRbacRole();
    try {
      const t = getAuthToken();
      if (!t) {
        router.replace(`/login?redirect=${encodeURIComponent(pathname || "/portal-cliente/mis-portes")}`);
        return;
      }
      if (role !== "cliente") {
        router.replace("/dashboard");
      }
    } catch {
      router.replace("/login");
    }
  }, [router, pathname]);

  const logout = () => {
    try {
      clearAuthToken();
      notifyJwtUpdated();
    } catch {
      /* ignore */
    }
    router.replace("/login");
  };

  return (
    <PortalClienteOnboardingProvider>
    <div className={cn("min-h-screen font-sans antialiased", dark ? "dark" : "")}>
      <div className="flex min-h-screen bg-zinc-100 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <aside className="hidden w-56 shrink-0 flex-col border-r border-zinc-200/80 bg-white dark:border-zinc-800 dark:bg-zinc-900/95 md:flex">
          <div className="flex items-center gap-2 border-b border-zinc-200/80 px-4 py-5 dark:border-zinc-800">
            <Image
              src="/logo.png"
              alt="AB Logistics logo"
              width={40}
              height={40}
              className="h-8 w-8 md:h-10 md:w-10 object-contain"
              priority
            />
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {p.badge}
              </p>
              <p className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-50">AB Logistics OS</p>
            </div>
          </div>
          <nav className="flex flex-1 flex-col gap-0.5 p-2">
            {nav.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname?.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition",
                    active
                      ? "bg-zinc-900 text-white shadow-sm dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800/80",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="flex flex-col gap-2 border-t border-zinc-200/80 p-3 dark:border-zinc-800">
            <nav className="flex flex-col gap-1.5 text-[11px] font-medium">
              {footerLinks.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="text-zinc-500 transition hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  {label}
                </Link>
              ))}
              <a
                href={portalSupportMailto()}
                className="text-zinc-500 transition hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
              >
                {p.footer.support}
              </a>
            </nav>
            {showApiDebug ? (
              <p className="truncate font-mono text-[10px] text-zinc-400" title={API_BASE}>
                {p.footer.apiDebugPrefix}
                {apiHostShort}
              </p>
            ) : (
              <p className="text-[10px] leading-snug text-zinc-500 dark:text-zinc-400">{p.footer.productNote}</p>
            )}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-zinc-200/80 bg-white/90 px-4 py-3 backdrop-blur-md dark:border-zinc-800 dark:bg-zinc-900/80">
            <div className="flex min-w-0 items-center gap-2 md:hidden">
              <Image
                src="/logo.png"
                alt="AB Logistics logo"
                width={40}
                height={40}
                className="h-8 w-8 object-contain"
                priority
              />
              <span className="truncate text-sm font-semibold">{p.mobileHeader}</span>
            </div>
            <div className="flex flex-1 items-center justify-end gap-2">
              <LocaleSwitcher className="border-zinc-200 dark:border-zinc-700" />
              <button
                type="button"
                onClick={() => setDark((d) => !d)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-700 shadow-sm transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
                aria-label={dark ? p.themeLight : p.themeDark}
              >
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <button
                type="button"
                onClick={logout}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-800 shadow-sm transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
              >
                <LogOut className="h-4 w-4" aria-hidden />
                <span className="hidden sm:inline">{p.signOut}</span>
              </button>
            </div>
          </header>

          <div className="border-b border-zinc-200/80 bg-white px-2 py-2 dark:border-zinc-800 dark:bg-zinc-900 md:hidden">
            <div className="flex gap-1 overflow-x-auto">
              {nav.map(({ href, label, icon: Icon }) => {
                const active = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium",
                      active ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "text-zinc-600",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>

          <main className="flex-1 overflow-x-hidden px-4 py-6 sm:px-8">{children}</main>

          <footer className="border-t border-zinc-200/80 bg-white/95 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/90 md:hidden">
            <nav className="flex flex-wrap gap-x-4 gap-y-2 text-xs font-medium">
              {footerLinks.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="text-zinc-600 underline-offset-2 hover:text-zinc-900 hover:underline dark:text-zinc-300 dark:hover:text-white"
                >
                  {label}
                </Link>
              ))}
              <a
                href={portalSupportMailto()}
                className="text-zinc-600 underline-offset-2 hover:text-zinc-900 hover:underline dark:text-zinc-300 dark:hover:text-white"
              >
                {p.footer.support}
              </a>
            </nav>
            {showApiDebug ? (
              <p className="mt-2 truncate font-mono text-[10px] text-zinc-400" title={API_BASE}>
                {p.footer.apiDebugPrefix}
                {apiHostShort}
              </p>
            ) : (
              <p className="mt-2 text-[10px] leading-snug text-zinc-500 dark:text-zinc-400">{p.footer.productNote}</p>
            )}
          </footer>
        </div>
      </div>
      <PortalClienteRiskModal />
    </div>
    </PortalClienteOnboardingProvider>
  );
}
