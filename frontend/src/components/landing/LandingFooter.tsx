"use client";

import Link from "next/link";
import Image from "next/image";
import { Mail } from "lucide-react";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingFooter() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing;

  return (
    <footer className="border-t border-zinc-800 bg-zinc-950 px-4 py-14 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-10 lg:flex-row lg:justify-between lg:items-start">
          <div>
            <Link href="/" className="flex items-center gap-2 text-white font-bold text-lg">
              <Image
                src="/logo.png"
                alt={l.brandAlt}
                width={40}
                height={40}
                className="h-8 w-8 md:h-10 md:w-10 object-contain"
                priority
              />
              AB Logistics OS
            </Link>
            <p className="mt-3 text-sm text-zinc-500 max-w-xs">
              {l.footer.description}
            </p>
          </div>
          <div className="flex flex-wrap gap-10 sm:gap-16">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">{l.footer.legal}</p>
              <ul className="space-y-2 text-sm">
                <li>
                  <a href="/legal" className="text-zinc-400 hover:text-white transition">
                    {l.footer.legalNotice}
                  </a>
                </li>
                <li>
                  <a href="/privacidad" className="text-zinc-400 hover:text-white transition">
                    {l.footer.privacy}
                  </a>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">{l.footer.contact}</p>
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
            <p className="text-xs text-zinc-500 mb-3">{l.footer.readyQuestion}</p>
            <Link
              href="/login"
              className="inline-flex rounded-full border border-emerald-500/50 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-400 hover:bg-emerald-500/20 transition"
            >
              {l.footer.salesCta}
            </Link>
          </div>
        </div>
        <p className="mt-12 pt-8 border-t border-zinc-800 text-center text-xs text-zinc-600">
          © {new Date().getFullYear()} AB Software. {l.footer.copyright}
        </p>
      </div>
    </footer>
  );
}
