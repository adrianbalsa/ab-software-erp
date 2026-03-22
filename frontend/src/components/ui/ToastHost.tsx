"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

export type ToastTone = "success" | "error" | "info";

export type ToastPayload = {
  id: number;
  message: string;
  tone: ToastTone;
};

type Props = {
  toast: ToastPayload | null;
  onDismiss: () => void;
  durationMs?: number;
};

/**
 * Toast accesible sin dependencias extra (Tailwind).
 * Sustituye por sonner/react-hot-toast si se añaden al proyecto.
 */
export function ToastHost({ toast, onDismiss, durationMs = 5200 }: Props) {
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(t);
  }, [toast, onDismiss, durationMs]);

  if (!toast) return null;

  const bg =
    toast.tone === "success"
      ? "bg-emerald-600 border-emerald-500"
      : toast.tone === "error"
        ? "bg-red-600 border-red-500"
        : "bg-slate-800 border-slate-600";

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 left-1/2 z-[100] flex w-[min(100%-2rem,28rem)] -translate-x-1/2 opacity-100 transition-opacity duration-300"
    >
      <div
        className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-sm font-medium text-white shadow-xl ${bg}`}
      >
        <p className="flex-1 leading-snug">{toast.message}</p>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-lg p-1 text-white/90 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-white/40"
          aria-label="Cerrar aviso"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
