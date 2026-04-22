"use client";

import Link from "next/link";
import Image from "next/image";
import { Mail } from "lucide-react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingFooter() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing;

  return (
    <footer className="border-t border-zinc-800 bg-surface-base px-4 py-14 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-10 lg:flex-row lg:justify-between lg:items-start">
          <div>
            <Link href="/" className="inline-flex min-h-11 items-center gap-2 py-1 text-white font-bold text-lg">
              <Image
                src="/logo.png"
                alt={l.brandAlt}
                width={40}
                height={40}
                className="h-8 w-8 md:h-10 md:w-10 object-contain"
                sizes="(max-width: 640px) 32px, 40px"
                priority
              />
              AB Logistics OS
            </Link>
            <p className="mt-3 text-sm text-zinc-400 max-w-xs">
              {l.footer.description}
            </p>
          </div>
          <div className="flex flex-wrap gap-10 sm:gap-16">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">{l.footer.legal}</p>
              <ul className="space-y-2 text-sm">
                <li>
                  <Link href="/aviso-legal" className="inline-flex min-h-11 items-center text-zinc-300 hover:text-white transition">
                    {l.footer.legalNotice}
                  </Link>
                </li>
                <li>
                  <Link href="/privacidad" className="inline-flex min-h-11 items-center text-zinc-300 hover:text-white transition">
                    {l.footer.privacy}
                  </Link>
                </li>
                <li>
                  <Link href="/cookies" className="inline-flex min-h-11 items-center text-zinc-300 hover:text-white transition">
                    {l.footer.cookies}
                  </Link>
                </li>
                <li>
                  <Link href="/terminos" className="inline-flex min-h-11 items-center text-zinc-300 hover:text-white transition">
                    {l.footer.terms}
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">{l.footer.contact}</p>
              <a
                href="mailto:comercial@ablogistics.os"
                className="inline-flex min-h-11 items-center gap-2 text-sm text-emerald-400/90 hover:text-emerald-300"
              >
                <Mail className="h-4 w-4" />
                comercial@ablogistics.os
              </a>
            </div>
          </div>
          <div className="lg:text-right">
            <p className="text-xs text-zinc-400 mb-3">{l.footer.readyQuestion}</p>
            <Link
              href="/login"
              className="inline-flex min-h-11 items-center rounded-full border border-emerald-500/50 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-400 hover:bg-emerald-500/20 transition"
            >
              {l.footer.salesCta}
            </Link>
          </div>
        </div>
        <p className="mt-12 pt-8 border-t border-zinc-800 text-center text-xs text-zinc-400">
          © {new Date().getFullYear()} AB Software. {l.footer.copyright}
        </p>
      </div>
    </footer>
  );
}
