"use client";

import Link from "next/link";
import {
  Car,
  CreditCard,
  FileText,
  LayoutDashboard,
  Leaf,
  Package,
  Receipt,
  Settings,
  Shield,
  Truck,
} from "lucide-react";
import type { ReactNode } from "react";

import { QuotaStatusCard } from "@/components/QuotaStatusCard";

const navLink =
  "flex items-center px-3 py-2.5 rounded-lg transition-colors text-sm font-medium";
const navInactive = "hover:bg-slate-800/80 hover:text-white text-slate-300";
const navActive = "bg-[#2563eb]/15 text-[#60a5fa] border border-[#2563eb]/25";

type Props = {
  children: ReactNode;
  active:
    | "dashboard"
    | "finanzas"
    | "portes"
    | "sostenibilidad"
    | "facturas"
    | "gastos"
    | "admin"
    | "seguridad"
    | "flota";
};

export function AppShell({ children, active }: Props) {
  return (
    <div className="flex min-h-screen ab-app-gradient font-sans text-slate-800">
      <aside
        className="w-64 shrink-0 flex flex-col border-r border-slate-800/80 text-slate-300"
        style={{
          background: "linear-gradient(180deg, #0b1224 0%, #060a14 100%)",
        }}
      >
        <div className="h-16 flex items-center px-6 border-b border-slate-800/80">
          <Truck className="w-6 h-6 text-[#60a5fa] mr-2" />
          <span className="text-white font-bold text-lg tracking-tight">
            AB Logistics OS
          </span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1">
          <Link
            href="/dashboard"
            className={`${navLink} ${active === "dashboard" ? navActive : navInactive}`}
          >
            <LayoutDashboard className="w-5 h-5 mr-3 shrink-0" />
            Dashboard
          </Link>
          <Link
            href="/finanzas"
            className={`${navLink} ${active === "finanzas" ? navActive : navInactive}`}
          >
            <FileText className="w-5 h-5 mr-3 shrink-0" />
            Finanzas
          </Link>
          <Link
            href="/portes"
            className={`${navLink} ${active === "portes" ? navActive : navInactive}`}
          >
            <Truck className="w-5 h-5 mr-3 shrink-0" />
            Portes
          </Link>
          <Link
            href="/flota"
            className={`${navLink} ${active === "flota" ? navActive : navInactive}`}
          >
            <Car className="w-5 h-5 mr-3 shrink-0" />
            Flota
          </Link>
          <Link
            href="/sostenibilidad"
            className={`${navLink} ${active === "sostenibilidad" ? navActive : navInactive}`}
          >
            <Package className="w-5 h-5 mr-3 shrink-0" />
            Sostenibilidad
          </Link>
          <Link
            href="/facturas"
            className={`${navLink} ${active === "facturas" ? navActive : navInactive}`}
          >
            <Receipt className="w-5 h-5 mr-3 shrink-0" />
            Facturas
          </Link>
          <Link
            href="/gastos"
            className={`${navLink} ${active === "gastos" ? navActive : navInactive}`}
          >
            <CreditCard className="w-5 h-5 mr-3 shrink-0" />
            Gastos
          </Link>
          <Link
            href="/admin"
            className={`${navLink} ${active === "admin" ? navActive : navInactive}`}
          >
            <Settings className="w-5 h-5 mr-3 shrink-0" />
            Admin
          </Link>
          <Link
            href="/perfil/seguridad"
            className={`${navLink} ${active === "seguridad" ? navActive : navInactive}`}
          >
            <Shield className="w-5 h-5 mr-3 shrink-0" />
            Seguridad
          </Link>
        </nav>
        <div className="px-4 pb-3 shrink-0">
          <QuotaStatusCard />
        </div>
        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-500 flex items-center gap-2">
          <Leaf className="w-4 h-4 text-emerald-500" />
          <span>AB Logistics OS</span>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">{children}</div>
    </div>
  );
}
