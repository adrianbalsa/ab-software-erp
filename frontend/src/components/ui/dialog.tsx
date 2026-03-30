"use client";

import * as React from "react";

function joinClasses(...parts: Array<string | undefined>) {
  return parts.filter(Boolean).join(" ");
}

type DialogCtx = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const Ctx = React.createContext<DialogCtx | null>(null);

export function Dialog({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}) {
  return <Ctx.Provider value={{ open, onOpenChange }}>{children}</Ctx.Provider>;
}

export function DialogContent({
  className,
  children,
  "aria-describedby": describedBy,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(Ctx);
  if (!ctx?.open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="Cerrar"
        onClick={() => ctx.onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-describedby={describedBy}
        className={joinClasses(
          "relative z-10 w-full max-w-lg rounded-2xl border border-zinc-200 bg-white p-0 shadow-lg",
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={joinClasses("border-b border-zinc-100 px-6 py-4", className)} {...props} />;
}

export function DialogTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={joinClasses("text-lg font-semibold text-zinc-900", className)} {...props} />
  );
}

export function DialogDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={joinClasses("text-sm text-zinc-500 mt-1", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={joinClasses("flex justify-end gap-2 border-t border-zinc-100 px-6 py-4", className)} {...props} />
  );
}
