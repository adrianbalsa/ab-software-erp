/**
 * Certificados ESG: PDF generado exclusivamente en FastAPI (`/api/v1/esg/certificates/...`).
 */

import type { FacturaPdfData, PorteDetailOut } from "@/lib/api";
import { downloadEsgCertificatePdf } from "@/lib/api";

export async function generateEsgCertificadoFromPorte(porte: PorteDetailOut): Promise<Blob> {
  return downloadEsgCertificatePdf("porte", String(porte.id));
}

export async function generateEsgCertificadoFromFactura(pdf: FacturaPdfData): Promise<Blob> {
  return downloadEsgCertificatePdf("factura", String(pdf.factura_id));
}
