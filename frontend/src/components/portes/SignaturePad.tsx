"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import SignatureCanvas from "react-signature-canvas";

export type SignaturePadSubmitPayload = {
  firma_b64: string;
  nombre_consignatario: string;
  /** DNI/NIE opcional (POD). */
  dni_consignatario?: string;
};

type SignaturePadProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Se llama al pulsar «Guardar firma» con PNG data URL y datos del receptor. */
  onSave: (payload: SignaturePadSubmitPayload) => void | Promise<void>;
  title?: string;
};

/**
 * Modal móvil para captura POD: canvas táctil (`touch-none`), nombre del receptor y DNI opcional.
 * Usar con `dynamic(..., { ssr: false })` si el padre es Server Component.
 */
export function SignaturePad({
  open,
  onOpenChange,
  onSave,
  title = "Firma de entrega (POD)",
}: SignaturePadProps) {
  const sigRef = useRef<SignatureCanvas>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [canvasW, setCanvasW] = useState(320);
  const [nombre, setNombre] = useState("");
  const [dni, setDni] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setCanvasW(Math.max(280, Math.floor(el.offsetWidth)));
    });
    ro.observe(el);
    setCanvasW(Math.max(280, Math.floor(el.offsetWidth)));
    return () => ro.disconnect();
  }, [open]);

  useEffect(() => {
    if (!open) {
      setErr(null);
      sigRef.current?.clear();
    }
  }, [open]);

  const limpiar = useCallback(() => {
    sigRef.current?.clear();
    setErr(null);
  }, []);

  const guardarFirma = useCallback(async () => {
    const n = nombre.trim();
    if (n.length < 2) {
      setErr("Indique el nombre completo del consignatario.");
      return;
    }
    const sig = sigRef.current;
    if (!sig || sig.isEmpty()) {
      setErr("La firma es obligatoria.");
      return;
    }
    setErr(null);
    setBusy(true);
    try {
      await onSave({
        firma_b64: sig.toDataURL("image/png"),
        nombre_consignatario: n,
        dni_consignatario: dni.trim() || undefined,
      });
      setNombre("");
      setDni("");
      sig.clear();
      onOpenChange(false);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar la firma");
    } finally {
      setBusy(false);
    }
  }, [dni, nombre, onOpenChange, onSave]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/75 backdrop-blur-[2px]"
        aria-label="Cerrar"
        onClick={() => !busy && onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal
        aria-labelledby="signature-pad-title"
        className="relative z-10 flex max-h-[min(96dvh,880px)] w-full max-w-lg flex-col rounded-t-2xl border border-zinc-700 bg-zinc-950 shadow-2xl sm:rounded-2xl"
      >
        <div className="shrink-0 border-b border-zinc-800 px-4 py-3">
          <h2 id="signature-pad-title" className="text-center text-lg font-semibold text-white">
            {title}
          </h2>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-5 pt-3">
          <label className="mb-1 block text-sm font-medium text-zinc-400">
            Nombre y apellidos del consignatario
          </label>
          <input
            type="text"
            autoComplete="name"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Quien recibe la mercancía"
            disabled={busy}
            className="mb-3 w-full min-h-12 rounded-xl border border-zinc-700 bg-zinc-900 px-4 text-base text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />

          <label className="mb-1 block text-sm font-medium text-zinc-400">DNI / NIE (opcional)</label>
          <input
            type="text"
            autoComplete="off"
            inputMode="text"
            value={dni}
            onChange={(e) => setDni(e.target.value)}
            placeholder="12345678A"
            disabled={busy}
            className="mb-4 w-full min-h-11 rounded-xl border border-zinc-700 bg-zinc-900 px-4 text-base text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />

          <p className="mb-2 text-sm font-medium text-zinc-300">Firma del consignatario</p>
          <div ref={wrapRef} className="w-full touch-none">
            <SignatureCanvas
              ref={sigRef}
              penColor="#34d399"
              backgroundColor="rgba(9, 9, 11, 1)"
              canvasProps={{
                width: canvasW,
                height: 256,
                className:
                  "h-64 w-full touch-none rounded-xl border-2 border-emerald-600/40 bg-zinc-950",
              }}
            />
          </div>

          {err ? (
            <p className="mt-3 rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-100">
              {err}
            </p>
          ) : null}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={limpiar}
              disabled={busy}
              className="min-h-12 flex-1 rounded-xl border-2 border-zinc-600 bg-zinc-900 text-base font-semibold text-zinc-200 active:bg-zinc-800 disabled:opacity-50"
            >
              Limpiar
            </button>
            <button
              type="button"
              onClick={() => void guardarFirma()}
              disabled={busy}
              className="min-h-12 flex-[1.1] rounded-xl bg-emerald-600 text-base font-bold text-white shadow-lg shadow-emerald-900/40 active:bg-emerald-500 disabled:opacity-50"
            >
              {busy ? "Guardando…" : "Guardar firma"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
