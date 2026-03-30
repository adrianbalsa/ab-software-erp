"use client";

import { AlertTriangle, CheckCircle, Clock, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type VeriFactuBadgeProps = {
  estado?: string | null;
  descripcion?: string | null;
};

export function VeriFactuBadge({ estado, descripcion }: VeriFactuBadgeProps) {
  const normalized = (estado ?? "").trim().toLowerCase();
  const desc = descripcion?.trim() || "Sin detalle AEAT.";

  let label = "Pendiente AEAT";
  /** Texto oscuro + borde marcado (WCAG AA en exteriores / alto brillo). */
  let className = "bg-slate-200 text-slate-900 border-2 border-slate-600";
  let Icon = Clock;

  if (normalized === "aceptado") {
    label = "Aceptada";
    className = "bg-emerald-100 text-emerald-950 border-2 border-emerald-800";
    Icon = CheckCircle;
  } else if (normalized === "aceptado_con_errores") {
    label = "Con Errores";
    className = "bg-amber-100 text-amber-950 border-2 border-amber-800";
    Icon = AlertTriangle;
  } else if (normalized === "rechazado" || normalized === "error_tecnico") {
    label = "Rechazada";
    className = "bg-red-100 text-red-950 border-2 border-red-800";
    Icon = XCircle;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span>
            <Badge className={`gap-1.5 ${className}`}>
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {label}
            </Badge>
          </span>
        </TooltipTrigger>
        <TooltipContent>{desc}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
