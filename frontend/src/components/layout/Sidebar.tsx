"use client";

import Link from "next/link";
import { LogOut, Webhook } from "lucide-react";
import { useMemo } from "react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { isOwnerLike, isTrafficManager, jwtDisplayName, jwtPayload, type AppRbacRole } from "@/lib/api";
import { logout } from "@/lib/auth";
import { useRole } from "@/hooks/useRole";
import { sidebarNavIcon, sidebarNavRow } from "@/components/layout/sidebarNavStyles";

type Props = {
  active?: string;
  role: AppRbacRole;
  onNavLinkClick?: () => void;
};

/** API y Webhooks (solo owner / admin / developer). */
export function ConfiguracionNavSection({ active, role, onNavLinkClick }: Props) {
  const { catalog } = useOptionalLocaleCatalog();
  if (isTrafficManager(role)) return null;
  if (!isOwnerLike(role) && role !== "developer") return null;

  const p = onNavLinkClick ? { onClick: onNavLinkClick } : {};
  const isActive = active === "desarrolladores";

  return (
    <Link
      href="/dashboard/configuracion/desarrolladores"
      className={sidebarNavRow(isActive)}
      {...p}
    >
      <Webhook className={sidebarNavIcon(isActive)} aria-hidden />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span>{catalog.sidebar.developerApi}</span>
        <span className="text-[11px] font-normal leading-snug text-zinc-500 group-hover:text-zinc-400">
          {catalog.sidebar.developerApiSub}
        </span>
      </span>
    </Link>
  );
}

function initialsFromSubject(sub: string): string {
  const s = sub.trim();
  if (!s) return "?";
  const at = s.indexOf("@");
  const local = at >= 0 ? s.slice(0, at) : s;
  const parts = local.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase().slice(0, 2);
  }
  return local.slice(0, 2).toUpperCase();
}

const DEMO_EMPRESA_CODE = "DEMO-LOGISTICS-001";
const DEMO_EMPRESA_UUID = "406d68d7-52d8-5eb2-bff1-0a03095f7f6f";

/** Pie de sidebar: avatar, nombre, rol y cierre de sesión (estilo bunker). */
export function SidebarUserSection() {
  const { role } = useRole();
  const { catalog } = useOptionalLocaleCatalog();
  const roleLabels = catalog.sidebar.roleLabels as Record<AppRbacRole, string>;
  const displayName = jwtDisplayName();
  const payload = jwtPayload();
  const empresaClaim = String(
    payload?.empresa_id ??
      payload?.empresaId ??
      payload?.tenant_id ??
      payload?.tenantId ??
      "",
  ).trim();
  const isDemoMode =
    empresaClaim === DEMO_EMPRESA_CODE ||
    empresaClaim === DEMO_EMPRESA_UUID ||
    (typeof window !== "undefined" && window.localStorage.getItem("ab.demo_mode") === "1");
  const initials = useMemo(() => initialsFromSubject(displayName), [displayName]);

  return (
    <div className="border-t border-zinc-800/80 px-4 pt-4 pb-2 shrink-0">
      <div className="flex items-start gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-zinc-700/90 bg-zinc-800/90 text-xs font-semibold uppercase tracking-tight text-zinc-100 shadow-inner"
          aria-hidden
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p className="truncate text-sm font-medium text-zinc-100" title={displayName}>
            {displayName}
          </p>
          <p className="truncate text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            {roleLabels[role] ?? role}
          </p>
          {isDemoMode && (
            <span className="mt-1 inline-flex items-center rounded-md border border-amber-700/60 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
              {catalog.sidebar.demoMode}
            </span>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={() => logout()}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2 text-xs font-semibold text-zinc-200 transition-all duration-200 hover:border-zinc-600 hover:bg-zinc-800/90 hover:text-white"
      >
        <LogOut className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
        {catalog.sidebar.logout}
      </button>
    </div>
  );
}
