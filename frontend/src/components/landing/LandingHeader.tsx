"use client";

import Link from "next/link";
import { Menu, Truck, X } from "lucide-react";
import { useState } from "react";

const nav = [
  { href: "#roi-simulator", label: "Simulador" },
  { href: "#moats", label: "Ventaja" },
  { href: "#how-it-works", label: "Cómo funciona" },
  { href: "#pricing", label: "Precios" },
  { href: "#faq", label: "FAQ" },
];

export function LandingHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-white font-bold tracking-tight">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 shadow-lg shadow-blue-500/20">
            <Truck className="h-5 w-5 text-white" />
          </span>
          <span className="hidden sm:inline text-lg">AB Logistics OS</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-zinc-400">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="hover:text-emerald-400 transition-colors"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/login"
            className="hidden sm:inline text-sm font-medium text-zinc-300 hover:text-white transition-colors"
          >
            Iniciar sesión
          </Link>
          <Link
            href="/login"
            className="rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 px-4 py-2 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/25 hover:from-emerald-400 hover:to-emerald-500 transition-all"
          >
            Solicitar Acceso al Sistema
          </Link>
          <button
            type="button"
            className="md:hidden rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
            aria-expanded={open}
            aria-label="Menú"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="md:hidden border-t border-zinc-800 px-4 py-4 space-y-3 bg-zinc-950">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="block text-zinc-300 font-medium py-2"
              onClick={() => setOpen(false)}
            >
              {item.label}
            </a>
          ))}
          <Link href="/login" className="block text-blue-400 font-medium py-2" onClick={() => setOpen(false)}>
            Iniciar sesión
          </Link>
        </div>
      )}
    </header>
  );
}
