export type FinancialHealthCsvRow = {
  name: string;
  ingresos: number;
  gastos: number;
  co2_cost: number;
};

export function exportToCSV(rows: FinancialHealthCsvRow[], filename = "financial-health.csv"): void {
  const header = ["Fecha", "Ingresos", "Gastos", "Coste CO2"];
  const lines = rows.map((r) => [r.name, r.ingresos.toFixed(2), r.gastos.toFixed(2), r.co2_cost.toFixed(2)]);
  const csv = [header, ...lines].map((line) => line.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");

  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

