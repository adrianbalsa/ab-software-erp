"use client";

import * as React from "react";

type TooltipCtx = {
  open: boolean;
  setOpen: (open: boolean) => void;
};

const Ctx = React.createContext<TooltipCtx | null>(null);

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function Tooltip({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  return (
    <Ctx.Provider value={{ open, setOpen }}>
      <span className="relative inline-flex">{children}</span>
    </Ctx.Provider>
  );
}

export function TooltipTrigger({
  children,
  asChild,
}: {
  children: React.ReactNode;
  asChild?: boolean;
}) {
  const ctx = React.useContext(Ctx);
  if (!ctx) return <>{children}</>;

  const triggerProps = {
    onMouseEnter: () => ctx.setOpen(true),
    onMouseLeave: () => ctx.setOpen(false),
    onFocus: () => ctx.setOpen(true),
    onBlur: () => ctx.setOpen(false),
  };

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(
      children as React.ReactElement<Record<string, unknown>>,
      triggerProps,
    );
  }

  return (
    <button type="button" {...triggerProps}>
      {children}
    </button>
  );
}

export function TooltipContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ctx = React.useContext(Ctx);
  if (!ctx?.open) return null;

  return (
    <div
      role="tooltip"
      className={joinClasses(
        "absolute left-1/2 top-full z-50 mt-2 w-max max-w-80 -translate-x-1/2 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-white shadow-lg",
        className,
      )}
    >
      {children}
    </div>
  );
}
