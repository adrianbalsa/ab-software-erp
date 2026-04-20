import { apiFetchJson } from "../lib/api";
import type { GastoCreateInput, GastoOcrExtract, GastoRecent } from "../types/gasto";

function buildTicketFormData(uri: string): FormData {
  const fd = new FormData();
  fd.append("evidencia", {
    uri,
    type: "image/jpeg",
    name: `ticket_${Date.now()}.jpg`,
  } as unknown as Blob);
  return fd;
}

export async function fetchRecentGastos(): Promise<GastoRecent[]> {
  return apiFetchJson<GastoRecent[]>("/api/v1/gastos/", { method: "GET" });
}

export async function ocrGastoFromTicket(ticketUri: string): Promise<GastoOcrExtract> {
  return apiFetchJson<GastoOcrExtract>("/api/v1/gastos/ocr", {
    method: "POST",
    body: buildTicketFormData(ticketUri),
  });
}

export async function createGastoOnline(input: GastoCreateInput): Promise<GastoRecent> {
  const fd = buildTicketFormData(input.ticketUri);
  fd.append("proveedor", input.proveedor);
  fd.append("fecha", input.fecha);
  fd.append("total_chf", String(input.total_chf));
  fd.append("categoria", input.categoria);
  fd.append("moneda", input.moneda);
  if (input.concepto) fd.append("concepto", input.concepto);
  if (input.nif_proveedor) fd.append("nif_proveedor", input.nif_proveedor);
  if (typeof input.iva === "number") fd.append("iva", String(input.iva));
  if (typeof input.total_eur === "number") fd.append("total_eur", String(input.total_eur));
  if (input.porte_id) fd.append("porte_id", input.porte_id);

  return apiFetchJson<GastoRecent>("/api/v1/gastos/", {
    method: "POST",
    body: fd,
  });
}
