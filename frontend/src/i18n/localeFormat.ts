export type MoneyLocale = "es" | "en";

export function currencyLocale(loc: MoneyLocale): string {
  return loc === "en" ? "en-GB" : "es-ES";
}

export function formatCurrencyEUR(
  value: number,
  loc: MoneyLocale,
  opts?: { maximumFractionDigits?: number },
): string {
  return value.toLocaleString(currencyLocale(loc), {
    style: "currency",
    currency: "EUR",
    ...(opts?.maximumFractionDigits != null
      ? { maximumFractionDigits: opts.maximumFractionDigits }
      : {}),
  });
}
