"use client";

import { QRCodeSVG } from "qrcode.react";

type InvoiceQRProps = {
  /** URL VeriFactu (SREI) devuelta por el backend, p. ej. ``verifactu_validation_url``. */
  url: string | null | undefined;
  /** Tamaño del QR en px (por defecto 120). */
  size?: number;
  className?: string;
};

/**
 * QR para previsualización en pantalla (el PDF sigue usando PNG en base64 desde el backend).
 */
export function InvoiceQR({ url, size = 120, className }: InvoiceQRProps) {
  const u = (url ?? "").trim();
  if (!u) {
    return (
      <div
        className={
          className ??
          "flex h-[120px] w-[120px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-400"
        }
        style={{ width: size, height: size }}
      >
        Sin URL VeriFactu
      </div>
    );
  }

  return (
    <div className={className} style={{ width: size, height: size }}>
      <QRCodeSVG
        value={u}
        size={size}
        level="M"
        includeMargin
        bgColor="#ffffff"
        fgColor="#18181b"
      />
    </div>
  );
}
