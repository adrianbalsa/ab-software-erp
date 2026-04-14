"use client";

import { QRCodeSVG } from "qrcode.react";

type InvoiceQRProps = {
  /** URL VeriFactu (SREI) devuelta por el backend, p. ej. ``verifactu_validation_url``. */
  url: string | null | undefined;
  /** Huella de auditoría (64 hex) para badge VeriFactu en UI. */
  hash?: string | null | undefined;
  /** Tamaño del QR en px (por defecto 120). */
  size?: number;
  className?: string;
};

/**
 * QR para previsualización en pantalla (el PDF oficial usa jsPDF + librería QR).
 */
export function InvoiceQR({ url, hash, size = 120, className }: InvoiceQRProps) {
  const u = (url ?? "").trim();
  const h = (hash ?? "").trim();
  const showVfBadge = Boolean(u && h && h.length === 64);

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
    <div className="flex flex-col items-center gap-2">
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
      {showVfBadge && (
        <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-800">VeriFactu</p>
      )}
      <p className="max-w-[200px] text-center text-[10px] text-slate-500">
        Factura verificable en la sede electrónica de la AEAT / VERIFACTU
      </p>
    </div>
  );
}
