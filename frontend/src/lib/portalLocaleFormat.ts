import type { AppLocale } from "@/i18n/catalog";

/** BCP 47 tag for `Intl` formatters from app locale. */
export function intlLocaleForApp(locale: AppLocale): string {
  return locale === "en" ? "en-GB" : "es-ES";
}

/** Fecha/hora corta para tablas del portal (portes). */
export function formatPortalDateTime(
  iso: string | null | undefined,
  locale: AppLocale,
  empty: string,
): string {
  if (!iso) return empty;
  const tag = intlLocaleForApp(locale);
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
    return d.toLocaleString(tag, {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(iso).slice(0, 10);
  }
}

export function formatPortalDecimal(
  value: number,
  locale: AppLocale,
  maximumFractionDigits: number,
): string {
  return value.toLocaleString(intlLocaleForApp(locale), { maximumFractionDigits });
}
