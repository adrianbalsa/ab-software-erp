/**
 * Certificado formal de huella de CO₂ (ISO 14001 / reporting) — estética zinc + esmeralda.
 */

import { jsPDF } from "jspdf";

import type { FacturaPdfData, PorteDetailOut } from "@/lib/api";

import { loadSvgLogoAsPngDataUrl } from "@/lib/exportUtils";

const MARGIN = 16;
const Z_BG: [number, number, number] = [24, 24, 27];
const Z_PANEL: [number, number, number] = [39, 39, 42];
const EM: [number, number, number] = [16, 185, 129];
const EM_DARK: [number, number, number] = [5, 150, 105];
const TXT: [number, number, number] = [244, 244, 245];
const MUTED: [number, number, number] = [161, 161, 170];

const fmtKm = (n: number) =>
  `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(n)} km`;
const fmtKg = (n: number) =>
  `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 3, minimumFractionDigits: 0 }).format(n)} kg CO₂`;

function vehiculoDescripcion(p: PorteDetailOut): string {
  const parts = [
    p.vehiculo_matricula,
    p.vehiculo_modelo,
    p.vehiculo_normativa_euro ? `Normativa: ${p.vehiculo_normativa_euro}` : null,
    p.vehiculo_engine_class ? `Motor (GLEC): ${p.vehiculo_engine_class}` : null,
    p.vehiculo_fuel_type ? `Combustible: ${p.vehiculo_fuel_type}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Vehículo no asignado en el registro del porte.";
}

/** Panel zinc con borde sutil; devuelve la Y inferior para seguir maquetando. */
function appendPanel(doc: jsPDF, y: number, pageW: number, title: string, lines: string[]): number {
  const pad = 5;
  const innerW = pageW - MARGIN * 2 - pad * 2;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  let contentH = 0;
  const chunks: string[][] = [];
  for (const ln of lines) {
    const w = doc.splitTextToSize(ln, innerW);
    chunks.push(w);
    contentH += w.length * 4.2 + 2;
  }
  const boxH = pad * 2 + 10 + contentH;
  doc.setFillColor(...Z_PANEL);
  doc.setDrawColor(63, 63, 70);
  doc.roundedRect(MARGIN, y, pageW - MARGIN * 2, boxH, 2, 2, "FD");
  let cy = y + pad + 7;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(...EM);
  doc.text(title, MARGIN + pad, cy);
  cy += 10;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...TXT);
  for (const w of chunks) {
    doc.text(w, MARGIN + pad, cy);
    cy += w.length * 4.2 + 2;
  }
  return y + boxH + 6;
}

export async function generateEsgCertificadoFromPorte(porte: PorteDetailOut): Promise<Blob> {
  const co2 =
    porte.esg_co2_total_kg != null && Number.isFinite(Number(porte.esg_co2_total_kg))
      ? Number(porte.esg_co2_total_kg)
      : null;
  const base =
    porte.esg_co2_euro_iii_baseline_kg != null && Number.isFinite(Number(porte.esg_co2_euro_iii_baseline_kg))
      ? Number(porte.esg_co2_euro_iii_baseline_kg)
      : null;
  const ahorro =
    porte.esg_co2_ahorro_vs_euro_iii_kg != null && Number.isFinite(Number(porte.esg_co2_ahorro_vs_euro_iii_kg))
      ? Number(porte.esg_co2_ahorro_vs_euro_iii_kg)
      : base != null && co2 != null
        ? Math.max(0, base - co2)
        : null;

  const logo = await loadSvgLogoAsPngDataUrl("/logo.svg");
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();

  doc.setFillColor(...Z_BG);
  doc.rect(0, 0, W, H, "F");

  doc.setDrawColor(...EM);
  doc.setLineWidth(1.2);
  doc.line(MARGIN, 18, W - MARGIN, 18);

  let y = 14;
  if (logo) {
    doc.setFillColor(250, 250, 250);
    doc.roundedRect(MARGIN, y, 14, 14, 1.5, 1.5, "F");
    try {
      doc.addImage(logo, "PNG", MARGIN + 1, y + 1, 12, 12);
    } catch {
      /* ignore logo raster errors */
    }
  }

  doc.setTextColor(...TXT);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(15);
  doc.text("Certificado de Eficiencia Logística y Huella de Carbono", MARGIN + (logo ? 24 : 0), y + 9, {
    maxWidth: W - MARGIN * 2 - (logo ? 20 : 0),
  });

  y = logo ? 34 : 28;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...MUTED);
  doc.text(
    "Documento orientado a evidencias para sistemas de gestión ambiental (p. ej. ISO 14001). Los importes de GEI se expresan como masa de CO₂ equivalente.",
    MARGIN,
    y,
    { maxWidth: W - MARGIN * 2 },
  );
  y += 14;

  y = appendPanel(doc, y, W, "Identificación del servicio", [
    `ID ruta / porte: ${porte.id}`,
    `Fecha operativa: ${String(porte.fecha || "—").slice(0, 10)}`,
    `Origen → Destino: ${porte.origen} → ${porte.destino}`,
    `Distancia declarada: ${fmtKm(Number(porte.km_estimados) || 0)} (km del registro; habitualmente estimados vía Google Directions en la fase de cotización/alta).`,
  ]);

  y = appendPanel(doc, y, W, "Vehículo y normativa de emisiones", [vehiculoDescripcion(porte)]);

  y = appendPanel(doc, y, W, "Resultados de huella (motor GLEC)", [
    co2 != null
      ? `Emisiones de GEI del transporte (CO₂): ${fmtKg(co2)}.`
      : "No se pudo calcular la huella GLEC (faltan datos de vehículo o distancia).",
    base != null ? `Línea base Euro III (mismo recorrido y combustible): ${fmtKg(base)}.` : "",
    ahorro != null ? `Ahorro estimado frente a Euro III: ${fmtKg(ahorro)}.` : "",
  ].filter(Boolean));

  doc.setFontSize(7.5);
  doc.setTextColor(...MUTED);
  const legal = doc.splitTextToSize(
    "Metodología: modelo GLEC simplificado de la plataforma (gramos CO₂ por km en tramo cargado y en vacío, según clase de motor y combustible del vehículo). " +
      "La referencia Euro III usa el mismo recorrido y combustible con factores de motor Euro III. " +
      "Los valores son estimaciones operativas; no sustituyen medición directa ni verificación de terceros.",
    W - MARGIN * 2,
  );
  doc.text(legal, MARGIN, Math.min(y, H - 28));

  doc.setTextColor(...EM_DARK);
  doc.setFont("helvetica", "italic");
  doc.setFontSize(7);
  doc.text(`Emitido: ${new Date().toLocaleString("es-ES")} · AB Logistics OS`, W / 2, H - 10, { align: "center" });

  return doc.output("blob");
}

export async function generateEsgCertificadoFromFactura(pdf: FacturaPdfData): Promise<Blob> {
  if (
    pdf.esg_total_co2_kg == null ||
    pdf.esg_euro_iii_baseline_kg == null ||
    pdf.esg_total_km == null ||
    pdf.esg_portes_count == null
  ) {
    throw new Error(
      "Esta factura no tiene agregado ESG en el servidor (sin portes vinculados o datos incompletos).",
    );
  }

  const co2 = Number(pdf.esg_total_co2_kg);
  const base = Number(pdf.esg_euro_iii_baseline_kg);
  const km = Number(pdf.esg_total_km);
  const ahorro =
    pdf.esg_ahorro_vs_euro_iii_kg != null
      ? Number(pdf.esg_ahorro_vs_euro_iii_kg)
      : Math.max(0, base - co2);

  const logo = await loadSvgLogoAsPngDataUrl("/logo.svg");
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();

  doc.setFillColor(...Z_BG);
  doc.rect(0, 0, W, H, "F");
  doc.setDrawColor(...EM);
  doc.setLineWidth(1.2);
  doc.line(MARGIN, 18, W - MARGIN, 18);

  let y = 14;
  if (logo) {
    doc.setFillColor(250, 250, 250);
    doc.roundedRect(MARGIN, y, 14, 14, 1.5, 1.5, "F");
    try {
      doc.addImage(logo, "PNG", MARGIN + 1, y + 1, 12, 12);
    } catch {
      /* ignore */
    }
  }
  doc.setTextColor(...TXT);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(15);
  doc.text("Certificado de Eficiencia Logística y Huella de Carbono", MARGIN + (logo ? 24 : 0), y + 9, {
    maxWidth: W - MARGIN * 2 - (logo ? 20 : 0),
  });
  y = logo ? 34 : 28;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...MUTED);
  doc.text(
    `Alcance: factura ${pdf.num_factura_verifactu || pdf.numero_factura} · Cliente: ${pdf.receptor.nombre}.`,
    MARGIN,
    y,
    { maxWidth: W - MARGIN * 2 },
  );
  y += 12;

  y = appendPanel(doc, y, W, "Identificación", [
    `ID documento: FACT-${pdf.factura_id}`,
    `Fecha de emisión fiscal: ${String(pdf.fecha_emision).slice(0, 10)}`,
    `Portes incluidos en el agregado: ${pdf.esg_portes_count}`,
    `Kilómetros operativos sumados: ${fmtKm(km)}.`,
  ]);

  y = appendPanel(doc, y, W, "Huella de GEI agregada (GLEC)", [
    `Emisiones de CO₂ equivalentes (transporte): ${fmtKg(co2)}.`,
    `Línea base Euro III (misma distancia y estructura por porte): ${fmtKg(base)}.`,
    `Ahorro estimado frente a Euro III: ${fmtKg(ahorro)}.`,
  ]);

  doc.setFontSize(7.5);
  doc.setTextColor(...MUTED);
  const legal = doc.splitTextToSize(
    "Metodología: suma de los modelos GLEC por cada porte facturado, con referencia Euro III homogénea por porte. " +
      "La distancia mostrada es la suma de kilómetros estimados de los portes vinculados a la factura.",
    W - MARGIN * 2,
  );
  doc.text(legal, MARGIN, Math.min(y, H - 28));

  doc.setTextColor(...EM_DARK);
  doc.setFont("helvetica", "italic");
  doc.setFontSize(7);
  doc.text(`Emitido: ${new Date().toLocaleString("es-ES")} · AB Logistics OS`, W / 2, H - 10, { align: "center" });

  return doc.output("blob");
}
