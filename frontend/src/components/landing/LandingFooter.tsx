"use client";

import Link from "next/link";
import { Mail, Truck } from "lucide-react";

export function LandingFooter() {
  return (
    <footer className="border-t border-zinc-800 bg-zinc-950 px-4 py-14 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-10 lg:flex-row lg:justify-between lg:items-start">
          <div>
            <Link href="/" className="flex items-center gap-2 text-white font-bold text-lg">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600">
                <Truck className="h-5 w-5 text-white" />
              </span>
              AB Logistics OS
            </Link>
            <p className="mt-3 text-sm text-zinc-500 max-w-xs">
              Sistema operativo para flotas, finanzas y cumplimiento fiscal.
            </p>
          </div>
          <div className="flex flex-wrap gap-10 sm:gap-16">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">Legal</p>
              <ul className="space-y-2 text-sm">
                <li>
                  <a href="/legal" className="text-zinc-400 hover:text-white transition">
                    Aviso legal
                  </a>
                </li>
                <li>
                  <a href="/privacidad" className="text-zinc-400 hover:text-white transition">
                    Política de privacidad (RGPD)
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">Contacto</p>
              <a
                href="mailto:comercial@ablogistics.os"
                className="inline-flex items-center gap-2 text-sm text-emerald-400/90 hover:text-emerald-300"
              >
                <Mail className="h-4 w-4" />
                comercial@ablogistics.os
              </a>
            </div>
          </div>
          <div className="lg:text-right">
            <p className="text-xs text-zinc-500 mb-3">¿Listo para digitalizar tu flota?</p>
            <Link
              href="/login"
              className="inline-flex rounded-full border border-emerald-500/50 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-400 hover:bg-emerald-500/20 transition"
            >
              Hablar con ventas
            </Link>
          </div>
        </div>
        <p className="mt-12 pt-8 border-t border-zinc-800 text-center text-xs text-zinc-600">
          © {new Date().getFullYear()} AB Software. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  );
}
