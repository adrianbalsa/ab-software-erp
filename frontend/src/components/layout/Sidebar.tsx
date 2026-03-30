"use client";

import Link from "next/link";
import { Webhook } from "lucide-react";
import type { AppRbacRole } from "@/lib/api";

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
