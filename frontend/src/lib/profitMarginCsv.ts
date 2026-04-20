import type { ProfitMarginAnalytics } from "@/lib/api";

function csvCell(s: string): string {
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

/**
 * CSV alineado con webhooks salientes (`analytics.profit_margin.snapshot`):
 * primera línea comentada con el tipo de evento para trazabilidad en ETL.
 */
export function buildProfitMarginCsv(data: ProfitMarginAnalytics): string {
  const eventType = String(data.meta.webhook_event_type ?? "analytics.profit_margin.snapshot");
  const lines: string[] = [`# webhook_event_type=${csvCell(eventType)}`];
  lines.push(
    [
      "period_key",
      "period_label",
      "ingresos_totales",
      "gastos_combustible",
      "gastos_peajes",
      "gastos_otros",
      "gastos_totales",
      "margen_neto",
    ].join(","),
  );
  for (const r of data.series) {
    lines.push(
      [
        csvCell(r.period_key),
        csvCell(r.period_label),
        r.ingresos_totales,
        r.gastos_combustible,
        r.gastos_peajes,
        r.gastos_otros,
        r.gastos_totales,
        r.margen_neto,
      ].join(","),
    );
  }
  lines.push("");
  lines.push("# totals_rango");
  lines.push(
    [
      "ingresos_totales",
      "gastos_combustible",
      "gastos_peajes",
      "gastos_otros",
      "gastos_totales",
      "margen_neto",
    ].join(","),
  );
  const t = data.totals_rango;
  lines.push(
    [
      t.ingresos_totales,
      t.gastos_combustible,
      t.gastos_peajes,
      t.gastos_otros,
      t.gastos_totales,
      t.margen_neto,
    ].join(","),
  );
  return `\ufeff${lines.join("\n")}`;
}

export function downloadProfitMarginCsv(data: ProfitMarginAnalytics, filename: string): void {
  const blob = new Blob([buildProfitMarginCsv(data)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.click();
  URL.revokeObjectURL(url);
}
