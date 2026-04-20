import { decode } from "base64-arraybuffer";

import { ApiError, apiFetchJson } from "../lib/api";
import { getSupabaseClient } from "../lib/supabase";
import type { PodRegisterInput, PodRegisterResult, PorteDetail, PorteListItem } from "../types/porte";

type UploadTarget = "firma" | "albaran";

function extractBase64FromDataUrl(dataUrl: string): string {
  const trimmed = dataUrl.trim();
  const comma = trimmed.indexOf(",");
  if (trimmed.startsWith("data:") && comma >= 0) return trimmed.slice(comma + 1);
  return trimmed;
}

async function uploadPodAsset(params: {
  porteId: string;
  target: UploadTarget;
  mimeType: string;
  base64Body: string;
}): Promise<string> {
  const { porteId, target, mimeType, base64Body } = params;
  const supabase = getSupabaseClient();
  const ext = mimeType.includes("png") ? "png" : "jpg";
  const path = `pods/${porteId}/${target}-${Date.now()}.${ext}`;
  const bytes = decode(base64Body);

  const { error } = await supabase.storage.from("pod-assets").upload(path, bytes, {
    contentType: mimeType,
    upsert: false,
  });
  if (error) throw new Error(`Upload ${target} fallido: ${error.message}`);

  const pub = supabase.storage.from("pod-assets").getPublicUrl(path);
  if (!pub.data.publicUrl) throw new Error(`No se pudo obtener URL pública para ${target}`);
  return pub.data.publicUrl;
}

async function photoUriToBase64(photoUri: string): Promise<string> {
  const res = await fetch(photoUri);
  if (!res.ok) throw new Error("No se pudo leer la foto del albarán");
  const bytes = await res.arrayBuffer();
  const uint = new Uint8Array(bytes);
  let binary = "";
  for (let i = 0; i < uint.length; i += 1) {
    binary += String.fromCharCode(uint[i]);
  }
  // React Native incluye global btoa.
  return btoa(binary);
}

export async function fetchPortesPendientes(): Promise<PorteListItem[]> {
  return apiFetchJson<PorteListItem[]>("/api/v1/portes/", { method: "GET" });
}

export async function fetchPorteDetail(porteId: string): Promise<PorteDetail> {
  return apiFetchJson<PorteDetail>(`/api/v1/portes/${porteId}`, { method: "GET" });
}

/**
 * Contrato objetivo Fase 4.2:
 * - upload de assets a Supabase
 * - PATCH /api/v1/portes/{id} con URLs + geostamp + estado entregado
 *
 * Fallback para backend actual:
 * - POST /api/v1/portes/{id}/firmar-entrega
 */
export async function registerPODOnline(input: PodRegisterInput): Promise<PodRegisterResult> {
  const signatureB64 = extractBase64FromDataUrl(input.signatureDataUrl);
  const photoB64 = await photoUriToBase64(input.photoUri);

  const [signatureUrl, photoUrl] = await Promise.all([
    uploadPodAsset({
      porteId: input.porteId,
      target: "firma",
      mimeType: "image/png",
      base64Body: signatureB64,
    }),
    uploadPodAsset({
      porteId: input.porteId,
      target: "albaran",
      mimeType: "image/jpeg",
      base64Body: photoB64,
    }),
  ]);

  try {
    const patchOut = await apiFetchJson<{ estado?: string; fecha_entrega_real?: string }>(
      `/api/v1/portes/${input.porteId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          estado: "ENTREGADO",
          pod_signature_url: signatureUrl,
          pod_photo_url: photoUrl,
          pod_geostamp: input.geostamp,
          nombre_consignatario_final: input.nombreConsignatario,
          dni_consignatario: input.dniConsignatario || null,
        }),
      },
    );
    return {
      estado: patchOut.estado ?? "ENTREGADO",
      fecha_entrega_real: patchOut.fecha_entrega_real,
      mode: "patch",
    };
  } catch (err) {
    if (!(err instanceof ApiError) || ![404, 405].includes(err.status)) throw err;
  }

  const fallback = await apiFetchJson<{ estado: string; fecha_entrega_real: string }>(
    `/api/v1/portes/${input.porteId}/firmar-entrega`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        firma_b64: input.signatureDataUrl,
        nombre_consignatario: input.nombreConsignatario,
        dni_consignatario: input.dniConsignatario || null,
      }),
    },
  );

  return {
    estado: fallback.estado,
    fecha_entrega_real: fallback.fecha_entrega_real,
    mode: "fallback_firmar_entrega",
  };
}
