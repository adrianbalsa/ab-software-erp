"use client";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import type { AppLocale } from "@/i18n/catalog";
import { cn } from "@/lib/utils";

export function LocaleSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, catalog } = useOptionalLocaleCatalog();

  const pill = (code: AppLocale, label: string) => (
    <button
      key={code}
      type="button"
      onClick={() => setLocale(code)}
      className={cn(
        "rounded-md px-2 py-1 text-xs font-semibold transition",
        locale === code
          ? "bg-emerald-600 text-zinc-950"
          : "text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200",
      )}
      aria-pressed={locale === code}
    >
      {label}
    </button>
  );

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-lg border border-zinc-700/80 bg-zinc-900/50 p-0.5",
        className,
      )}
    >
      <span className="sr-only">{catalog.locale.label}</span>
      {pill("es", catalog.locale.es)}
      {pill("en", catalog.locale.en)}
    </div>
  );
}
