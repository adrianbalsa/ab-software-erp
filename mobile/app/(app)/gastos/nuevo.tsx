import { CameraView, useCameraPermissions } from "expo-camera";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useRef, useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { ApiError } from "../../../src/lib/api";
import { ocrGastoFromTicket } from "../../../src/services/gastosApi";
import { saveGasto } from "../../../src/services/sync_service";
import type { GastoCategoria, GastoOcrExtract } from "../../../src/types/gasto";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function errText(e: unknown): string {
  if (e instanceof ApiError) return typeof e.body === "string" ? e.body : JSON.stringify(e.body);
  if (e instanceof Error) return e.message;
  return "Error inesperado";
}

export default function NuevoGastoScreen() {
  const router = useRouter();
  const { porte_id } = useLocalSearchParams<{ porte_id?: string }>();
  const cameraRef = useRef<CameraView | null>(null);
  const [perm, requestPerm] = useCameraPermissions();
  const [ticketUri, setTicketUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [proveedor, setProveedor] = useState("");
  const [cif, setCif] = useState("");
  const [base, setBase] = useState("");
  const [iva, setIva] = useState("");
  const [total, setTotal] = useState("");
  const [fecha, setFecha] = useState(todayIso());
  const [categoria, setCategoria] = useState<GastoCategoria>("otros");
  const [concepto, setConcepto] = useState("Ticket OCR");
  const [porteId, setPorteId] = useState((porte_id || "").trim());

  const applyOCR = (ocr: GastoOcrExtract) => {
    if (ocr.proveedor) setProveedor(ocr.proveedor);
    if (ocr.cif) setCif(ocr.cif);
    if (typeof ocr.base_imponible === "number") setBase(String(ocr.base_imponible));
    if (typeof ocr.iva === "number") setIva(String(ocr.iva));
    if (typeof ocr.total === "number") setTotal(String(ocr.total));
    if (ocr.fecha) setFecha(String(ocr.fecha).slice(0, 10));
    const source = `${ocr.proveedor || ""} ${ocr.cif || ""}`.toLowerCase();
    if (source.includes("repsol") || source.includes("cepsa") || source.includes("bp") || source.includes("shell")) {
      setCategoria("combustible");
    }
  };

  const captureAndScan = async () => {
    setError(null);
    if (!perm?.granted) {
      const p = await requestPerm();
      if (!p.granted) {
        setError("Permiso de cámara denegado");
        return;
      }
    }
    if (!cameraRef.current) return;
    setBusy(true);
    try {
      const shot = await cameraRef.current.takePictureAsync({ quality: 0.85, skipProcessing: true });
      if (!shot?.uri) throw new Error("No se pudo capturar imagen.");
      const optimized = await manipulateAsync(
        shot.uri,
        [{ resize: { width: 1280 } }],
        { compress: 0.72, format: SaveFormat.JPEG },
      );
      setTicketUri(optimized.uri);
      const ocr = await ocrGastoFromTicket(optimized.uri);
      applyOCR(ocr);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!ticketUri) {
      setError("Primero captura el ticket.");
      return;
    }
    if (!proveedor.trim() || !total.trim()) {
      setError("Proveedor y total son obligatorios.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await saveGasto({
        proveedor: proveedor.trim(),
        fecha: fecha.trim() || todayIso(),
        total_chf: Number(total),
        categoria,
        moneda: "EUR",
        concepto: concepto.trim() || undefined,
        nif_proveedor: cif.trim() || undefined,
        iva: iva.trim() ? Number(iva) : undefined,
        total_eur: total.trim() ? Number(total) : undefined,
        porte_id: porteId.trim() || undefined,
        ticketUri,
      });
      router.replace(created ? "/(app)/gastos" : "/(app)/pendientes");
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView className="flex-1 bg-slate-50" contentContainerStyle={{ padding: 16, paddingBottom: 28 }}>
      <View className="rounded-xl border border-slate-200 bg-white p-4">
        <Text className="text-base font-semibold text-slate-900">Escaneo OCR de ticket</Text>
        <Text className="mt-1 text-xs text-slate-500">Captura y compresión optimizada para ahorrar datos.</Text>

        <View className="mt-3 overflow-hidden rounded-lg border border-slate-200">
          <CameraView ref={cameraRef} style={{ height: 230 }} facing="back" />
        </View>
        <Pressable onPress={() => void captureAndScan()} className="mt-3 items-center rounded-lg bg-indigo-600 py-3">
          {busy ? <ActivityIndicator color="#fff" /> : <Text className="text-sm font-semibold text-white">Capturar + OCR</Text>}
        </Pressable>
        {ticketUri ? <Image source={{ uri: ticketUri }} style={{ height: 130, marginTop: 10, borderRadius: 8 }} /> : null}
      </View>

      <View className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <Text className="text-base font-semibold text-slate-900">Confirma datos del gasto</Text>
        {error ? (
          <View className="mt-2 rounded-lg bg-red-50 px-3 py-2">
            <Text className="text-sm text-red-800">{error}</Text>
          </View>
        ) : null}

        <TextInput value={proveedor} onChangeText={setProveedor} placeholder="Proveedor" className="mt-3 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={cif} onChangeText={setCif} placeholder="CIF/NIF" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={base} onChangeText={setBase} placeholder="Base imponible" keyboardType="decimal-pad" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={iva} onChangeText={setIva} placeholder="IVA" keyboardType="decimal-pad" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={total} onChangeText={setTotal} placeholder="Total" keyboardType="decimal-pad" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={fecha} onChangeText={setFecha} placeholder="YYYY-MM-DD" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <View className="mt-2 rounded-lg border border-slate-200 px-2 py-2">
          <Text className="mb-2 text-xs uppercase text-slate-500">Categoría</Text>
          <View className="flex-row flex-wrap gap-2">
            {(["combustible", "materiales", "servicios", "otros"] as const).map((c) => (
              <Pressable
                key={c}
                onPress={() => setCategoria(c)}
                className={`rounded-md px-3 py-2 ${categoria === c ? "bg-indigo-600" : "bg-slate-100"}`}
              >
                <Text className={`text-xs font-medium ${categoria === c ? "text-white" : "text-slate-700"}`}>{c}</Text>
              </Pressable>
            ))}
          </View>
        </View>
        <TextInput value={concepto} onChangeText={setConcepto} placeholder="Concepto" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />
        <TextInput value={porteId} onChangeText={setPorteId} placeholder="porte_id (opcional)" className="mt-2 rounded-lg border border-slate-200 px-3 py-3" />

        <Pressable onPress={() => void save()} disabled={busy} className="mt-4 items-center rounded-lg bg-emerald-600 py-3 disabled:opacity-50">
          {busy ? <ActivityIndicator color="#fff" /> : <Text className="text-sm font-semibold text-white">Guardar gasto</Text>}
        </Pressable>
      </View>
    </ScrollView>
  );
}
