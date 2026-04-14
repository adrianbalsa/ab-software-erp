import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

const A4_MARGIN_MM = 14;
const LOGO_MAX_MM = 12;

/** Convierte claves tipo API (`snake_case`) a encabezados PascalCase; respeta claves ya en PascalCase. */
export function apiKeyToPascalCase(key: string): string {
  if (key.includes("_")) {
    return key
      .split("_")
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())
      .join("");
  }
  if (/^[A-Z]/.test(key)) return key;
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function normalizeRowKeys(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    out[apiKeyToPascalCase(k)] = v;
  }
  return out;
}

function ensureFileExtension(name: string, ext: string): string {
  const e = ext.startsWith(".") ? ext : `.${ext}`;
  return name.toLowerCase().endsWith(e.toLowerCase()) ? name : `${name}${e}`;
}

function formatCellForPdf(value: unknown): string {
  if (value == null) return "";
  if (value instanceof Date) return value.toLocaleString("es-ES");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "";
  return String(value);
}

/** Rasteriza `/logo.svg` (u otra ruta pública) a PNG en data URL para jsPDF. */
export async function loadSvgLogoAsPngDataUrl(logoPath = "/logo.svg"): Promise<string | null> {
  if (typeof window === "undefined") return null;
  try {
    const res = await fetch(logoPath);
    if (!res.ok) return null;
    const svgText = await res.text();
    const blob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    return await new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        const w = img.naturalWidth || 64;
        const h = img.naturalHeight || 64;
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          URL.revokeObjectURL(url);
          resolve(null);
          return;
        }
        ctx.drawImage(img, 0, 0);
        let png: string;
        try {
          png = canvas.toDataURL("image/png");
        } catch {
          URL.revokeObjectURL(url);
          resolve(null);
          return;
        }
        URL.revokeObjectURL(url);
        resolve(png);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(null);
      };
      img.src = url;
    });
  } catch {
    return null;
  }
}

/**
 * Exporta filas a Excel con cabeceras PascalCase (desde `snake_case` o mezcla).
 */
export function exportToExcel(data: any[], fileName: string): void {
  const name = ensureFileExtension(fileName, ".xlsx");
  const rows =
    data.length > 0
      ? data.map((row) =>
          normalizeRowKeys(row && typeof row === "object" && !Array.isArray(row) ? (row as Record<string, unknown>) : {}),
        )
      : [normalizeRowKeys({ mensaje: "Sin datos" })];
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Datos");
  XLSX.writeFile(wb, name);
}

/**
 * PDF A4 con cabecera AB Logistics OS, logo (`/logo.svg` rasterizado) y marca de tiempo.
 * `columns` son los títulos de columna (PascalCase); cada fila en `data` debe exponer las mismas claves.
 */
export async function exportToPDF(
  data: any[],
  columns: string[],
  title: string,
  fileName: string,
): Promise<void> {
  const name = ensureFileExtension(fileName, ".pdf");
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const innerW = pageWidth - A4_MARGIN_MM * 2;

  const logo = await loadSvgLogoAsPngDataUrl("/logo.svg");
  let cursorY = A4_MARGIN_MM;

  if (logo) {
    doc.addImage(logo, "PNG", A4_MARGIN_MM, cursorY, LOGO_MAX_MM, LOGO_MAX_MM);
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(15, 23, 42);
  doc.text("AB Logistics OS", A4_MARGIN_MM + (logo ? LOGO_MAX_MM + 4 : 0), cursorY + 7);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(71, 85, 105);
  doc.text(title, A4_MARGIN_MM + (logo ? LOGO_MAX_MM + 4 : 0), cursorY + 13);

  const ts = new Date().toLocaleString("es-ES", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  doc.setFontSize(9);
  doc.setTextColor(100, 116, 139);
  doc.text(`Exportado: ${ts}`, pageWidth - A4_MARGIN_MM, cursorY + 7, { align: "right" });

  cursorY += logo ? LOGO_MAX_MM + 6 : 18;

  doc.setDrawColor(226, 232, 240);
  doc.setLineWidth(0.3);
  doc.line(A4_MARGIN_MM, cursorY, pageWidth - A4_MARGIN_MM, cursorY);
  cursorY += 4;

  const rowGet = (row: unknown, col: string): unknown =>
    row && typeof row === "object" && !Array.isArray(row)
      ? (row as Record<string, unknown>)[col]
      : undefined;

  const body =
    data.length === 0
      ? [columns.map(() => "—")]
      : data.map((row) => columns.map((c) => formatCellForPdf(rowGet(row, c))));

  autoTable(doc, {
    head: [columns],
    body,
    startY: cursorY,
    margin: { left: A4_MARGIN_MM, right: A4_MARGIN_MM, top: cursorY, bottom: A4_MARGIN_MM },
    styles: {
      fontSize: 7,
      cellPadding: 1.5,
      overflow: "linebreak",
      cellWidth: "wrap",
    },
    headStyles: {
      fillColor: [37, 99, 235],
      textColor: 255,
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [248, 250, 252] },
    tableWidth: innerW,
    theme: "striped",
    horizontalPageBreak: true,
  });

  doc.save(name);
}
