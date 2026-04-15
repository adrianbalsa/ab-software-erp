/**
 * PDF comercial VeriFactu (jsPDF) — QR mín. 20×20 mm, pie legal AEAT / VERIFACTU.
 */

import autoTable from "jspdf-autotable";
import { jsPDF } from "jspdf";
import QRCode from "qrcode";

import type { FacturaPdfData, VerifactuQrPreview } from "@/lib/api";

import { loadSvgLogoAsPngDataUrl } from "@/lib/exportUtils";

const MARGIN_MM = 14;
const QR_SIZE_MM = 20;
/** Consulta pública VeriFactu (misma base que ``build_srei_verifactu_url`` en backend). */
const SREI_VERIFACTU_BASE = "https://www2.agenciatributaria.gob.es/vlz/SREI/VERIFACTU";

const fmtEur = (n: number) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(n);

/** AEAT: fecha en parámetros de consulta pública (DD-MM-AAAA). */
export function fechaEmisionToDdMmYyyy(fechaEmision: string): string {
  const raw = (fechaEmision || "").trim().slice(0, 10);
  if (/^\d{2}-\d{2}-\d{4}$/.test(raw)) return raw;
  if (raw.length === 10 && raw[4] === "-" && raw[7] === "-") {
    const [y, m, d] = raw.split("-");
    return `${d}-${m}-${y}`;
  }
  return raw;
}

/**
 * URL SREI / VERIFACTU alineada con el backend (`aeat_qr_service.build_srei_verifactu_url`).
 * Preferir siempre `verifactu_validation_url` (persistido como `qr_code_url`) cuando exista.
 */
export function buildSreiVerifactuUrl(data: FacturaPdfData): string {
  const nif = encodeURIComponent((data.emisor.nif || "").trim());
  const numser = encodeURIComponent((data.num_factura_verifactu || data.numero_factura || "").trim());
  const fec = encodeURIComponent(fechaEmisionToDdMmYyyy(data.fecha_emision));
  const imp = encodeURIComponent(`${Number(data.total_factura).toFixed(2)}`);
  const huellaSource =
    (data.hash_registro || "").trim() ||
    (data.fingerprint_hash || "").trim() ||
    (data.fingerprint_completo || "").trim();
  const hc = huellaSource.slice(0, 8);
  let q = `nif=${nif}&numser=${numser}&fec=${fec}&imp=${imp}`;
  if (hc) {
    q += `&hc=${encodeURIComponent(hc)}`;
  }
  return `${SREI_VERIFACTU_BASE}?${q}`;
}

/** URL del QR: `verifactu_validation_url` (BD) o reconstrucción SREI con `hc` desde huellas del payload. */
export function resolveVerifactuQrUrl(data: FacturaPdfData): string {
  const persisted = (data.verifactu_validation_url || "").trim();
  if (persisted) return persisted;
  return buildSreiVerifactuUrl(data);
}

/** PNG data URL (alta resolución; el PDF lo escala a 20×20 mm). */
export async function generateVerifactuQrDataUrl(verificationUrl: string): Promise<string> {
  return QRCode.toDataURL(verificationUrl.trim(), {
    type: "image/png",
    errorCorrectionLevel: "M",
    margin: 2,
    width: 360,
    color: { dark: "#000000", light: "#ffffff" },
  });
}

export type VerifactuInvoicePdfInput = {
  pdfData: FacturaPdfData;
  /** Huella desde el módulo VeriFactu (`getQrPreview`), si está disponible. */
  verifactuPreview?: VerifactuQrPreview | null;
};

function resolveAuditHash(input: VerifactuInvoicePdfInput): string {
  const prev = input.verifactuPreview?.fingerprint_hash?.trim();
  if (prev) return prev;
  const a = (input.pdfData.verifactu_hash_audit || "").trim();
  if (a) return a;
  const fp = (input.pdfData.fingerprint_completo || "").trim();
  if (fp) return fp;
  return (input.pdfData.hash_registro || "").trim();
}

/**
 * Genera el PDF VeriFactu (cabecera con logo, líneas, IVA, pie legal y QR ≥ 20 mm).
 */
export async function generateVerifactuInvoicePdfBlob(input: VerifactuInvoicePdfInput): Promise<Blob> {
  const { pdfData: d } = input;
  const verificationUrl = resolveVerifactuQrUrl(d);
  const [logoDataUrl, qrDataUrl] = await Promise.all([
    loadSvgLogoAsPngDataUrl("/logo.svg"),
    generateVerifactuQrDataUrl(verificationUrl),
  ]);

  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const innerW = pageW - MARGIN_MM * 2;
  let y = MARGIN_MM;

  const numShow = d.num_factura_verifactu || d.numero_factura;
  const fechaLabel = String(d.fecha_emision).slice(0, 10);

  if (logoDataUrl) {
    doc.addImage(logoDataUrl, "PNG", MARGIN_MM, y, 12, 12);
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(24, 24, 27);
  doc.text("AB Logistics OS", MARGIN_MM + (logoDataUrl ? 16 : 0), y + 7);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(82, 82, 91);
  doc.text(d.emisor.nombre, MARGIN_MM + (logoDataUrl ? 16 : 0), y + 12);
  y += logoDataUrl ? 16 : 10;

  doc.setDrawColor(228, 228, 231);
  doc.setLineWidth(0.35);
  doc.line(MARGIN_MM, y, pageW - MARGIN_MM, y);
  y += 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(24, 24, 27);
  doc.text("FACTURA", MARGIN_MM, y + 6);

  doc.setFontSize(10);
  doc.setTextColor(82, 82, 91);
  const metaX = pageW - MARGIN_MM;
  let metaY = y;
  doc.text("Número", metaX, metaY, { align: "right" });
  metaY += 5;
  doc.setFont("helvetica", "bold");
  doc.setTextColor(24, 24, 27);
  doc.text(numShow, metaX, metaY, { align: "right" });
  metaY += 7;
  doc.setFont("helvetica", "normal");
  doc.setTextColor(82, 82, 91);
  doc.text("Fecha emisión", metaX, metaY, { align: "right" });
  metaY += 5;
  doc.setFont("helvetica", "bold");
  doc.setTextColor(24, 24, 27);
  doc.text(fechaLabel, metaX, metaY, { align: "right" });
  if (d.tipo_factura) {
    metaY += 7;
    doc.setFont("helvetica", "normal");
    doc.setTextColor(82, 82, 91);
    doc.text("Tipo", metaX, metaY, { align: "right" });
    metaY += 5;
    doc.setFont("helvetica", "bold");
    doc.setTextColor(24, 24, 27);
    doc.text(d.tipo_factura, metaX, metaY, { align: "right" });
  }

  y += 18;

  const colGap = 6;
  const colW = (innerW - colGap) / 2;
  doc.setFillColor(244, 244, 245);
  doc.roundedRect(MARGIN_MM, y, colW, 32, 2, 2, "F");
  doc.roundedRect(MARGIN_MM + colW + colGap, y, colW, 32, 2, 2, "F");
  doc.setDrawColor(228, 228, 231);
  doc.roundedRect(MARGIN_MM, y, colW, 32, 2, 2, "S");
  doc.roundedRect(MARGIN_MM + colW + colGap, y, colW, 32, 2, 2, "S");

  doc.setFont("helvetica", "bold");
  doc.setFontSize(7);
  doc.setTextColor(113, 113, 122);
  doc.text("EMISOR", MARGIN_MM + 3, y + 5);
  doc.text("CLIENTE", MARGIN_MM + colW + colGap + 3, y + 5);

  doc.setFontSize(10);
  doc.setTextColor(24, 24, 27);
  doc.text(d.emisor.nombre, MARGIN_MM + 3, y + 11, { maxWidth: colW - 6 });
  doc.text(d.receptor.nombre, MARGIN_MM + colW + colGap + 3, y + 11, { maxWidth: colW - 6 });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(63, 63, 70);
  doc.text(`NIF: ${d.emisor.nif || "—"}`, MARGIN_MM + 3, y + 18);
  doc.text(`NIF: ${d.receptor.nif || "—"}`, MARGIN_MM + colW + colGap + 3, y + 18);
  if (d.emisor.direccion) {
    doc.text(d.emisor.direccion, MARGIN_MM + 3, y + 24, { maxWidth: colW - 6 });
  }

  y += 38;

  const lineas =
    d.lineas.length > 0
      ? d.lineas
      : [{ concepto: "—", cantidad: 0, precio_unitario: 0, importe: 0 }];

  autoTable(doc, {
    startY: y,
    head: [["Concepto", "Cant.", "Precio u.", "Importe"]],
    body: lineas.map((ln) => [
      ln.concepto,
      String(ln.cantidad),
      fmtEur(ln.precio_unitario),
      fmtEur(ln.importe),
    ]),
    margin: { left: MARGIN_MM, right: MARGIN_MM },
    styles: { fontSize: 8, cellPadding: 2.5, textColor: [39, 39, 42] },
    headStyles: {
      fillColor: [228, 228, 231],
      textColor: [63, 63, 70],
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [250, 250, 250] },
    columnStyles: {
      0: { cellWidth: innerW * 0.46 },
      1: { halign: "right", cellWidth: innerW * 0.12 },
      2: { halign: "right", cellWidth: innerW * 0.21 },
      3: { halign: "right", cellWidth: innerW * 0.21, fontStyle: "bold" },
    },
  });

  const afterTable = (doc as jsPDF & { lastAutoTable?: { finalY?: number } }).lastAutoTable?.finalY;
  y = (typeof afterTable === "number" ? afterTable : y + 40) + 8;

  const boxW = 72;
  const boxX = pageW - MARGIN_MM - boxW;
  doc.setFillColor(244, 244, 245);
  doc.roundedRect(boxX, y, boxW, 34, 2, 2, "F");
  doc.setDrawColor(212, 212, 216);
  doc.roundedRect(boxX, y, boxW, 34, 2, 2, "S");

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(82, 82, 91);
  doc.text("Base imponible", boxX + 4, y + 8);
  doc.text(fmtEur(d.base_imponible), boxX + boxW - 4, y + 8, { align: "right" });
  doc.text(`IVA (${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(d.tipo_iva_porcentaje)} %)`, boxX + 4, y + 16);
  doc.text(fmtEur(d.cuota_iva), boxX + boxW - 4, y + 16, { align: "right" });
  doc.setDrawColor(24, 24, 27);
  doc.setLineWidth(0.4);
  doc.line(boxX + 3, y + 20, boxX + boxW - 3, y + 20);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(24, 24, 27);
  doc.text("Total", boxX + 4, y + 28);
  doc.text(fmtEur(d.total_factura), boxX + boxW - 4, y + 28, { align: "right" });

  y += 42;

  const auditHash = resolveAuditHash(input);
  const footerTop = Math.max(y, 250);
  const qrY = footerTop;

  doc.setDrawColor(212, 212, 216);
  doc.setLineWidth(0.25);
  doc.line(MARGIN_MM, qrY - 4, pageW - MARGIN_MM, qrY - 4);

  doc.addImage(qrDataUrl, "PNG", MARGIN_MM, qrY, QR_SIZE_MM, QR_SIZE_MM);

  const textX = MARGIN_MM + QR_SIZE_MM + 6;
  const textW = pageW - MARGIN_MM - textX;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8.5);
  doc.setTextColor(24, 24, 27);
  doc.text("Factura verificable en la sede electrónica de la AEAT / VERIFACTU", textX, qrY + 3, {
    maxWidth: textW,
  });

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(82, 82, 91);
  const legalLines = doc.splitTextToSize(
    "Este documento incluye un código QR conforme a especificaciones AEAT (tamaño mínimo 20×20 mm). " +
      "La verificación directa puede realizarse en la sede electrónica indicada.",
    textW,
  );
  doc.text(legalLines, textX, qrY + 10);

  let detailY = qrY + 10 + legalLines.length * 3.6 + 2;
  if (auditHash) {
    doc.setFont("courier", "normal");
    doc.setFontSize(6.8);
    doc.setTextColor(63, 63, 70);
    const hashLines = doc.splitTextToSize(`Huella / auditoría: ${auditHash}`, textW);
    doc.text(hashLines, textX, detailY);
    detailY += hashLines.length * 3.2 + 2;
  }

  if (d.aeat_csv_ultimo_envio) {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(6.5);
    doc.setTextColor(113, 113, 122);
    const csvLines = doc.splitTextToSize(`CSV AEAT (último envío): ${d.aeat_csv_ultimo_envio}`, textW);
    doc.text(csvLines, textX, detailY);
  }

  doc.setFont("helvetica", "italic");
  doc.setFontSize(6.5);
  doc.setTextColor(161, 161, 170);
  doc.text(
    "Documento generado electrónicamente · Importes con redondeo comercial (EUR)",
    pageW / 2,
    287,
    { align: "center" },
  );

  return doc.output("blob");
}
