"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, MapPin, Package, PenLine } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { API_BASE, authHeaders, parseApiError, postFirmaEntrega } from "@/lib/api";

const SignaturePadDynamic = dynamic(
  async () => {
    const mod = await import("@/components/portes/SignaturePad");
    return mod.SignaturePad;
  },
  { ssr: false },
);

type PorteResumen = {
  id: string;
  origen: string;
  destino: string;
  descripcion: string | null;
  bultos: number;
};

export default function EntregaDriverPage() {
  const params = useParams();
  const router = useRouter();
  const id = typeof params?.id === "string" ? params.id : "";

  const [porte, setPorte] = useState<PorteResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/portes/${encodeURIComponent(id)}`, {
        credentials: "include",
        headers: { ...authHeaders() },
      });
      if (!res.ok) {
        const msg = await parseApiError(res);
        throw new Error(msg);
      }
      const j = (await res.json()) as PorteResumen;
      setPorte(j);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar el porte");
      setPorte(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const onFirmaGuardada = useCallback(
    async (payload: {
      firma_b64: string;
      nombre_consignatario: string;
      dni_consignatario?: string;
    }) => {
      setError(null);
      setSubmitting(true);
      try {
        await postFirmaEntrega(id, payload);
        setSuccess(true);
        window.setTimeout(() => {
          router.push("/portes");
        }, 2000);
      } catch (e: unknown) {
        throw new Error(e instanceof Error ? e.message : "No se pudo registrar la entrega");
      } finally {
        setSubmitting(false);
      }
    },
    [id, router],
  );

  return (
    <div className="min-h-dvh bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-3">
          <Link
            href="/portes"
            className="min-h-11 min-w-11 shrink-0 rounded-lg border border-zinc-700 px-3 py-2 text-center text-sm font-medium text-emerald-400"
          >
            ← Rutas
          </Link>
          <h1 className="text-center text-base font-semibold tracking-tight text-white">
            Entrega digital
          </h1>
          <span className="min-w-11" aria-hidden />
        </div>
      </header>

      <main className="mx-auto max-w-lg px-4 pb-10 pt-4">
        {loading && (
          <div className="flex flex-col items-center gap-3 py-16 text-zinc-400">
            <Loader2 className="h-10 w-10 animate-spin text-emerald-500" aria-hidden />
            <p className="text-sm">Cargando porte…</p>
          </div>
        )}

        {!loading && error && !porte && (
          <div className="rounded-xl border border-red-900/60 bg-red-950/40 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        {porte && (
          <>
            <section className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 shadow-lg shadow-black/40">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-emerald-500/90">
                Resumen del servicio
              </p>
              <ul className="space-y-3 text-[15px] leading-snug">
                <li className="flex gap-2">
                  <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
                  <span>
                    <span className="font-medium text-zinc-300">Origen</span>
                    <br />
                    <span className="text-zinc-100">{porte.origen}</span>
                  </span>
                </li>
                <li className="flex gap-2">
                  <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
                  <span>
                    <span className="font-medium text-zinc-300">Destino</span>
                    <br />
                    <span className="text-zinc-100">{porte.destino}</span>
                  </span>
                </li>
                <li className="flex gap-2">
                  <Package className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
                  <span>
                    <span className="font-medium text-zinc-300">Mercancía</span>
                    <br />
                    <span className="text-zinc-100">{porte.descripcion?.trim() || "—"}</span>
                  </span>
                </li>
                <li className="rounded-lg bg-zinc-950/80 px-3 py-2 text-center text-lg font-semibold text-white">
                  Bultos a entregar: {porte.bultos}
                </li>
              </ul>
            </section>

            {error && porte && (
              <p className="mb-4 rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-100">
                {error}
              </p>
            )}

            <button
              type="button"
              onClick={() => {
                setError(null);
                setSignatureOpen(true);
              }}
              disabled={submitting || success}
              className="flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-900/40 active:bg-emerald-500 disabled:opacity-50"
            >
              <PenLine className="h-5 w-5 shrink-0" aria-hidden />
              {submitting ? "Enviando…" : "Abrir firma de entrega"}
            </button>

            <SignaturePadDynamic
              open={signatureOpen}
              onOpenChange={setSignatureOpen}
              onSave={onFirmaGuardada}
            />
          </>
        )}
      </main>

      <AnimatePresence>
        {success && (
          <motion.div
            className="fixed inset-0 z-20 flex items-center justify-center bg-black/70 px-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="flex max-w-sm flex-col items-center gap-4 rounded-2xl border border-emerald-500/40 bg-zinc-900 p-8 text-center shadow-2xl"
              initial={{ scale: 0.85, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 320, damping: 24 }}
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.1, type: "spring", stiffness: 400, damping: 15 }}
              >
                <CheckCircle2 className="h-20 w-20 text-emerald-400" strokeWidth={1.5} />
              </motion.div>
              <p className="text-xl font-semibold text-white">Entrega registrada</p>
              <p className="text-sm text-zinc-400">Volviendo a tus rutas…</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
