"use client";

import Link from "next/link";
import { LogOut, Webhook } from "lucide-react";
import { useMemo } from "react";
import { jwtSubject, type AppRbacRole } from "@/lib/api";
import { logout } from "@/lib/auth";
import { useRole } from "@/hooks/useRole";

const navLink =
  "flex items-center px-3 py-2.5 rounded-lg transition-colors text-sm font-medium";
const navInactive = "hover:bg-slate-800/80 hover:text-white text-slate-300";
const navActive = "bg-[#2563eb]/15 text-[#60a5fa] border border-[#2563eb]/25";

type Props = {
  active?: string;
  role: AppRbacRole;
  onNavLinkClick?: () => void;
};

/** Bloque «Configuración»: API y Webhooks (solo owner / developer). */
export function ConfiguracionNavSection({ active, role, onNavLinkClick }: Props) {
  if (role !== "owner" && role !== "developer") return null;

  const p = onNavLinkClick ? { onClick: onNavLinkClick } : {};

  return (
    <div className="pt-4 mt-2 border-t border-slate-800/80">
      <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        Configuración
      </p>
      <Link
        href="/dashboard/configuracion/desarrolladores"
        className={`${navLink} ${active === "desarrolladores" ? navActive : navInactive}`}
        {...p}
      >
        <Webhook className="w-5 h-5 mr-3 shrink-0" />
        API y Webhooks
      </Link>
    </div>
  );
}

const ROLE_LABELS: Record<AppRbacRole, string> = {
  owner: "Propietario",
  traffic_manager: "Traffic Manager",
  driver: "Conductor",
  cliente: "Cliente",
  developer: "Desarrollador",
};

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

/** Pie de sidebar: avatar, nombre, rol y cierre de sesión (estilo bunker). */
export function SidebarUserSection() {
  const { role } = useRole();
  const displayName = jwtSubject() || "Usuario";
  const initials = useMemo(() => initialsFromSubject(displayName), [displayName]);

  return (
    <div className="border-t border-slate-800/80 px-4 pt-4 pb-2 shrink-0">
      <div className="flex items-start gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-slate-700/90 bg-slate-800/90 text-xs font-semibold uppercase tracking-tight text-slate-100 shadow-inner"
          aria-hidden
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p className="truncate text-sm font-medium text-slate-100" title={displayName}>
            {displayName}
          </p>
          <p className="truncate text-[11px] font-medium uppercase tracking-wide text-slate-500">
            {ROLE_LABELS[role] ?? role}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => logout()}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700/80 bg-slate-900/50 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-600 hover:bg-slate-800/90 hover:text-white"
      >
        <LogOut className="h-4 w-4 shrink-0 opacity-90" aria-hidden />
        Cerrar sesión
      </button>
    </div>
  );
}
