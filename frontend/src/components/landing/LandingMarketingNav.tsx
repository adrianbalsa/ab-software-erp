"use client";

import Link from "next/link";
import Image from "next/image";

import { ThemeModeControl } from "@/components/ThemeModeControl";
import { LocaleSwitcher } from "@/components/i18n/LocaleSwitcher";
import { useOptionalLocaleCatalog } from "@/context/LocaleContext";

export function LandingMarketingNav() {
  const { catalog } = useOptionalLocaleCatalog();
  const n = catalog.nav;
  const l = catalog.landing;
  const s = catalog.appShell;
  const anchors = [
    { href: "#plataforma", label: l.nav.platform },
    { href: "#how-it-works", label: l.nav.howItWorks },
    { href: "#trust", label: l.nav.trust },
    { href: "#pricing", label: l.nav.pricing },
    { href: "#help", label: l.nav.help },
  ];
  return (
    <header className="sticky top-0 z-50 border-b border-zinc-200/90 dark:border-zinc-800/80 bg-surface-nav backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center gap-3 py-1 text-zinc-900 dark:text-white"
          aria-label={l.nav.homeAria}
        >
          <Image
            src="/logo.png"
            alt={l.brandAlt}
            width={40}
            height={40}
            className="h-8 w-8 md:h-10 md:w-10 shrink-0 object-contain"
            sizes="(max-width: 640px) 32px, 40px"
            priority
          />
          <span className="text-base font-semibold tracking-tight sm:text-lg">
            AB Logistics <span className="font-medium text-zinc-600 dark:text-zinc-400">OS</span>
          </span>
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <ThemeModeControl
            labels={{
              appearance: s.themeAppearance,
              light: s.themeLight,
              dark: s.themeDark,
              system: s.themeSystem,
            }}
          />
          <LocaleSwitcher />
          {anchors.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="inline-flex min-h-11 items-center rounded-full border border-transparent px-3 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-700 dark:text-zinc-300 transition hover:text-zinc-950 dark:hover:text-white"
            >
              {item.label}
            </a>
          ))}
          <Link
            href="/login"
            className="inline-flex min-h-11 items-center rounded-full border border-zinc-300 dark:border-zinc-700 bg-zinc-100/80 dark:bg-zinc-900/50 px-4 py-2 text-xs font-semibold uppercase tracking-widest text-zinc-700 dark:text-zinc-300 transition hover:border-emerald-500/40 hover:text-zinc-950 dark:hover:text-white"
          >
            {n.appLogin}
          </Link>
        </div>
      </div>
    </header>
  );
}
