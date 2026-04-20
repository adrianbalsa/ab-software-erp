"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Props = {
  children: ReactNode;
  className?: string;
  /** Sobre fondo oscuro (p. ej. tabla facturas portal). */
  variant?: "page" | "panel";
};

/** Errores del portal: anunciados a tecnologías de apoyo (`role="alert"`). */
export function PortalClienteAlert({ children, className, variant = "page" }: Props) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "rounded-lg border px-4 py-3 text-sm",
        variant === "panel"
          ? "border-red-500/30 bg-red-950/50 text-red-100"
          : "border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200",
        className,
      )}
    >
      {children}
    </div>
  );
}
