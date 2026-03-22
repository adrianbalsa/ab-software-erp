"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { FadeInSection } from "./FadeInSection";

const faqs = [
  {
    q: "¿Es difícil migrar mis datos actuales?",
    a: "No. Puedes importar clientes y flota de forma guiada, o empezar cargando solo portes y facturas nuevas. Nuestro equipo puede ayudarte en el primer mes si lo necesitas.",
  },
  {
    q: "¿Qué pasa si tengo menos de 5 camiones?",
    a: "El plan Starter está pensado precisamente para pequeñas flotas y autónomos: hasta 5 vehículos con VeriFactu completo. Sin penalización por ser pequeño.",
  },
  {
    q: "¿Cómo garantiza el software la ley VeriFactu?",
    a: "Cada factura genera un hash criptográfico encadenado con el registro anterior. Los datos son inmutables tras emitirse: la trazabilidad cumple los requisitos de la normativa AEAT y el SIF.",
  },
  {
    q: "¿Puedo probar antes de comprometerme?",
    a: "Sí. Puedes iniciar una prueba gratuita con acceso al dashboard y simuladores; sin tarjeta en el primer paso.",
  },
];

export function LandingFAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <FadeInSection id="faq" className="scroll-mt-24 px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Preguntas frecuentes</h2>
          <p className="mt-2 text-zinc-400 text-sm">Respuestas directas antes de dar el siguiente paso.</p>
        </div>
        <div className="space-y-3">
          {faqs.map((item, i) => {
            const isOpen = open === i;
            return (
              <div
                key={item.q}
                className="rounded-2xl border border-zinc-800 bg-zinc-900/50 overflow-hidden"
              >
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold text-white hover:bg-zinc-800/50 transition"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                >
                  {item.q}
                  <ChevronDown
                    className={`h-5 w-5 shrink-0 text-zinc-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-4 text-sm text-zinc-400 leading-relaxed border-t border-zinc-800/80 pt-3">
                    {item.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </FadeInSection>
  );
}
