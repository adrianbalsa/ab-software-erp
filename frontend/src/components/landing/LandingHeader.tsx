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
    <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-white font-bold tracking-tight">
          <Image
            src="/logo.png"
            alt={l.brandAlt}
            width={40}
            height={40}
            className="h-8 w-8 md:h-10 md:w-10 object-contain"
            priority
          />
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
            {l.nav.login}
          </Link>
          <Link
            href="/login"
            className="rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 px-4 py-2 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/25 hover:from-emerald-400 hover:to-emerald-500 transition-all"
          >
            {l.nav.requestAccess}
          </Link>
          <button
            type="button"
            className="md:hidden rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-white"
            aria-expanded={open}
            aria-label={l.nav.menuAria}
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
            {l.nav.login}
          </Link>
        </div>
      )}
    </header>
  );
}
