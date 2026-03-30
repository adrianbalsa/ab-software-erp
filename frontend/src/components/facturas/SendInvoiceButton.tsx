"use client";

import { useState } from "react";
import { Loader2, Mail } from "lucide-react";

import type { ToastTone } from "@/components/ui/ToastHost";
import { api, FacturaEmailSendError } from "@/lib/api";

type Props = {
  facturaId: number;
  onToast: (message: string, tone: ToastTone) => void;
};

/**
 * Envía la factura por correo (SMTP en backend). Toasts alineados con ``ToastHost`` de la página.
 */
export function SendInvoiceButton({ facturaId, onToast }: Props) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    setBusy(true);
    try {
      const out = await api.facturas.sendByEmail(facturaId);
      onToast(`Factura enviada correctamente a ${out.destinatario}`, "success");
    } catch (e) {
      if (e instanceof FacturaEmailSendError) {
        if (e.status === 400) {
          onToast("El cliente no tiene un email configurado", "error");
        } else if (e.status === 503) {
          onToast(
            "El envío por correo no está disponible: revise la configuración SMTP del búnker (servidor).",
            "error",
          );
        } else {
          onToast(e.message || "No se pudo enviar la factura por correo", "error");
        }
      } else {
        onToast("No se pudo enviar la factura por correo", "error");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      disabled={busy}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-transparent text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-50"
      title="Enviar factura por correo"
      aria-label="Enviar factura por correo electrónico"
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Mail className="h-4 w-4" aria-hidden />}
    </button>
  );
}
