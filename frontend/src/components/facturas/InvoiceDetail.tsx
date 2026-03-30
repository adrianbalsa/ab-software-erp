"use client";

import { QRCodeSVG } from "qrcode.react";
import { Shield, CheckCircle } from "lucide-react";

type InvoiceQRProps = {
  url: string | null | undefined;
  hash: string | null | undefined;
  size?: number;
  className?: string;
  showBadge?: boolean;
};

export function InvoiceQR({ url, hash, size = 120, className, showBadge = true }: InvoiceQRProps) {
  const u = (url ?? "").trim();
  const h = (hash ?? "").trim();
  const isValid = u && h && h.length === 64;

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
    <div className="flex flex-col items-center gap-3">
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
      {showBadge && isValid && (
        <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 border border-emerald-200">
          <Shield className="w-4 h-4 text-emerald-600" />
          <span className="text-xs font-semibold text-emerald-700">VeriFactu</span>
          <CheckCircle className="w-4 h-4 text-emerald-600" />
        </div>
      )}
      <p className="text-[10px] text-center text-slate-500 max-w-[160px]">
        Factura verificable en la sede electrónica de la AEAT
      </p>
    </div>
  );
}
