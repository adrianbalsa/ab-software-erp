"use client";

import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { FileDown, Printer, X } from "lucide-react";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

type Props = {
  open: boolean;
  title: string;
  pdfUrl: string | null;
  fileBaseName: string;
  onClose: () => void;
};

export function CmrPdfViewerModal({ open, title, pdfUrl, fileBaseName, onClose }: Props) {
  const [width, setWidth] = useState(720);

  useEffect(() => {
    if (!open) return;
    const vw =
      typeof window !== "undefined" ? Math.floor(window.innerWidth * 0.88) : 720;
    const w = typeof window !== "undefined" ? Math.min(800, vw) : 720;
    queueMicrotask(() => {
      setWidth(w);
    });
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-[min(1rem,4vw)]"
      style={{ background: "rgba(2, 6, 23, 0.75)" }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-[90vw] flex-col overflow-hidden rounded-2xl border border-slate-700 shadow-2xl"
        style={{
          background: "linear-gradient(180deg, #0f172a 0%, #020617 100%)",
        }}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-700 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-100 truncate pr-2">{title}</h2>
          <div className="flex items-center gap-2 shrink-0">
            {pdfUrl ? (
              <>
                <a
                  href={pdfUrl}
                  download={`${fileBaseName}.pdf`}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                >
                  <FileDown className="w-4 h-4" />
                  Descargar
                </a>
                <button
                  type="button"
                  onClick={() => window.open(pdfUrl, "_blank", "noopener,noreferrer")}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
                >
                  <Printer className="w-4 h-4" />
                  Abrir / imprimir
                </button>
              </>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center justify-center rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
              aria-label="Cerrar"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 bg-slate-900/50">
          {!pdfUrl ? (
            <p className="text-sm text-slate-500 text-center py-12">Sin documento.</p>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Document
                file={pdfUrl}
                loading={
                  <p className="text-sm text-slate-400 py-12">Cargando PDF…</p>
                }
                error={
                  <p className="text-sm text-red-300 py-12">
                    No se pudo mostrar el visor. Usa Descargar o abre en nueva pestaña.
                  </p>
                }
              >
                <Page pageNumber={1} width={width} className="shadow-lg" />
              </Document>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
