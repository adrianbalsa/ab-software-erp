"use client";

import * as React from "react";

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

type SheetCtx = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const SheetContext = React.createContext<SheetCtx | null>(null);

/** Contenedor tipo Shadcn: estado open + panel lateral (solo &lt; lg en AppShell). */
export function Sheet({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <SheetContext.Provider value={{ open, onOpenChange }}>{children}</SheetContext.Provider>
  );
}

export function SheetContent({
  side = "left",
  className,
  style,
  children,
  "aria-label": ariaLabel = "Menú de navegación",
}: {
  side?: "left" | "right";
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
  "aria-label"?: string;
}) {
  const ctx = React.useContext(SheetContext);
  if (!ctx?.open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-[60] bg-black/60 lg:hidden"
        aria-label="Cerrar menú"
        onClick={() => ctx.onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        style={style}
        className={joinClasses(
          "fixed inset-y-0 z-[70] flex w-[min(100%,20rem)] max-w-[100vw] flex-col overflow-hidden shadow-2xl lg:hidden",
          side === "left" ? "left-0 border-r" : "right-0 border-l",
          "border-slate-800/80",
          className,
        )}
      >
        {children}
      </div>
    </>
  );
}

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={joinClasses("shrink-0 border-b border-slate-800/80", className)} {...props} />;
}

export function SheetTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={joinClasses("text-base font-bold text-white tracking-tight", className)} {...props} />
  );
}
