"use client";

import Link from "next/link";
import Image from "next/image";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingHeader() {
  const [open, setOpen] = useState(false);
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing;
  const nav = [
    { href: "#roi-simulator", label: l.nav.simulator },
    { href: "#moats", label: l.nav.advantage },
    { href: "#how-it-works", label: l.nav.howItWorks },
    { href: "#pricing", label: l.nav.pricing },
    { href: "#help", label: l.nav.help },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-surface-nav-strong backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="inline-flex min-h-11 items-center gap-2 py-1 text-white font-bold tracking-tight">
          <Image
            src="/logo.png"
            alt={l.brandAlt}
            width={40}
            height={40}
            className="h-8 w-8 md:h-10 md:w-10 object-contain"
            sizes="(max-width: 640px) 32px, 40px"
            priority
          />
          <span className="hidden sm:inline text-lg">AB Logistics OS</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-zinc-300">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="inline-flex min-h-11 items-center py-1 hover:text-emerald-400 transition-colors"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/login"
            className="hidden sm:inline-flex min-h-11 items-center text-sm font-medium text-zinc-300 hover:text-white transition-colors"
          >
            {l.nav.login}
          </Link>
          <Link
            href="/login"
            className="inline-flex min-h-11 items-center rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 px-4 py-2 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/25 hover:from-emerald-400 hover:to-emerald-500 transition-all"
          >
            {l.nav.requestAccess}
          </Link>
          <button
            type="button"
            className="md:hidden min-h-11 min-w-11 rounded-lg p-2 text-zinc-300 hover:bg-zinc-800 hover:text-white"
            aria-expanded={open}
            aria-label={l.nav.menuAria}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      <div
        className={`transform-gpu overflow-hidden border-t border-zinc-800 bg-surface-base px-4 transition-[max-height,opacity,transform] duration-200 ease-out motion-reduce:transition-none md:hidden ${
          open ? "max-h-96 py-4 opacity-100 translate-y-0" : "max-h-0 py-0 opacity-0 -translate-y-1 pointer-events-none"
        }`}
      >
        <div className="space-y-2">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="block min-h-11 py-2 text-zinc-300 font-medium"
              onClick={() => setOpen(false)}
            >
              {item.label}
            </a>
          ))}
          <Link
            href="/login"
            className="block min-h-11 py-2 text-blue-400 font-medium"
            onClick={() => setOpen(false)}
          >
            {l.nav.login}
          </Link>
        </div>
      </div>
    </header>
  );
}
