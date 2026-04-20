import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
import { useLocalSearchParams, useRouter } from "expo-router";
import SignatureScreen from "react-native-signature-canvas";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { ApiError } from "../../../src/lib/api";
import { fetchPorteDetail } from "../../../src/services/portesApi";
import { registerPOD } from "../../../src/services/sync_service";
import type { PodGeoStamp, PorteDetail } from "../../../src/types/porte";

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail === null || detail === undefined) return "Error";
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function PorteDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const porteId = useMemo(() => String(id || "").trim(), [id]);
  const cameraRef = useRef<CameraView | null>(null);

  const [cameraPerm, requestCameraPerm] = useCameraPermissions();
  const [signatureDataUrl, setSignatureDataUrl] = useState<string | null>(null);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [geostamp, setGeostamp] = useState<PodGeoStamp | null>(null);
  const [consignatario, setConsignatario] = useState("");
  const [dni, setDni] = useState("");
  const [showSignaturePad, setShowSignaturePad] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [porte, setPorte] = useState<PorteDetail | null>(null);

  const load = useCallback(async () => {
    if (!porteId) return;
    setError(null);
    try {
      const out = await fetchPorteDetail(porteId);
      setPorte(out);
      if (out.nombre_consignatario_final) setConsignatario(out.nombre_consignatario_final);
    } catch (e) {
      if (e instanceof ApiError) setError(formatDetail(e.body));
      else if (e instanceof Error) setError(e.message);
      else setError("No se pudo cargar el detalle del porte");
    } finally {
      setLoading(false);
    }
  }, [porteId]);

  useEffect(() => {
    void load();
  }, [load]);

  const capturePhoto = useCallback(async () => {
    setError(null);
    if (!cameraPerm?.granted) {
      const perm = await requestCameraPerm();
      if (!perm.granted) {
        setError("Permiso de cámara denegado.");
        return;
      }
    }
    if (!cameraRef.current) return;
    const pic = await cameraRef.current.takePictureAsync({
      quality: 0.7,
      skipProcessing: true,
    });
    if (pic?.uri) {
      setPhotoUri(pic.uri);
      setShowCamera(false);
    }
  }, [cameraPerm?.granted, requestCameraPerm]);

  const captureLocationStamp = useCallback(async () => {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (!perm.granted) throw new Error("Permiso de ubicación denegado.");
    const pos = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.High,
    });
    return {
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
      captured_at: new Date().toISOString(),
    } satisfies PodGeoStamp;
  }, []);

  const onSignatureOK = useCallback(
    async (sigDataUrl: string) => {
      try {
        const stamp = await captureLocationStamp();
        setSignatureDataUrl(sigDataUrl);
        setGeostamp(stamp);
        await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        setShowSignaturePad(false);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      }
    },
    [captureLocationStamp],
  );

  const onSubmit = useCallback(async () => {
    if (!porteId) return;
    setSuccess(null);
    setError(null);
    if (!consignatario.trim()) {
      setError("Debes indicar el nombre del receptor.");
      return;
    }
    if (!signatureDataUrl) {
      setError("Falta capturar la firma.");
      return;
    }
    if (!photoUri) {
      setError("Falta capturar la foto del albarán.");
      return;
    }
    if (!geostamp) {
      setError("Falta geostamp de firma. Repite la firma.");
      return;
    }

    setSaving(true);
    try {
      const out = await registerPOD({
        porteId,
        nombreConsignatario: consignatario.trim(),
        dniConsignatario: dni.trim() || undefined,
        signatureDataUrl,
        photoUri,
        geostamp,
      });
      const warning =
        out.mode === "fallback_firmar_entrega"
          ? " (modo compatibilidad: backend sin PATCH aún)"
          : out.mode === "queued_offline"
            ? " (sin red: guardado en cola para sincronizar)"
          : "";
      setSuccess(`Entrega registrada: ${out.estado}${warning}`);
      await load();
    } catch (e) {
      if (e instanceof ApiError) setError(formatDetail(e.body));
      else if (e instanceof Error) setError(e.message);
      else setError("No se pudo registrar la entrega.");
    } finally {
      setSaving(false);
    }
  }, [consignatario, dni, geostamp, load, photoUri, porteId, signatureDataUrl]);

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!porte) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50 px-5">
        <Text className="text-center text-slate-700">No se encontró el porte.</Text>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-slate-50" contentContainerStyle={{ padding: 16, paddingBottom: 32 }}>
      <View className="rounded-xl border border-slate-200 bg-white p-4">
        <Text className="text-xs font-medium uppercase text-slate-500">{porte.fecha}</Text>
        <Text className="mt-1 text-lg font-semibold text-slate-900">
          {porte.origen} → {porte.destino}
        </Text>
        <Text className="mt-2 text-sm text-slate-600">
          Estado: {porte.estado} · {porte.km_estimados} km
        </Text>
        {porte.fecha_entrega_real ? (
          <Text className="mt-1 text-sm text-emerald-700">Entregado en: {porte.fecha_entrega_real}</Text>
        ) : null}
        {porte.estado.toLowerCase() === "entregado" ? (
          <View className="mt-3 flex-row gap-2">
            <Pressable
              onPress={() => router.push(`/(app)/porte/preview-${porte.id}`)}
              className="self-start rounded-lg bg-slate-900 px-3 py-2 active:opacity-80"
            >
              <Text className="text-xs font-semibold text-white">Previsualizar albarán legal (PDF)</Text>
            </Pressable>
            <Pressable
              onPress={() => router.push(`/(app)/gastos/nuevo?porte_id=${porte.id}`)}
              className="self-start rounded-lg bg-indigo-600 px-3 py-2 active:opacity-80"
            >
              <Text className="text-xs font-semibold text-white">Añadir gasto</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      <View className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <Text className="text-base font-semibold text-slate-900">Registrar Entrega (POD)</Text>
        <Text className="mt-1 text-xs text-slate-500">
          Captura firma, foto y geolocalización del momento de firma.
        </Text>

        <Text className="mt-4 text-xs font-medium uppercase text-slate-500">Receptor</Text>
        <TextInput
          value={consignatario}
          onChangeText={setConsignatario}
          placeholder="Nombre y apellidos"
          className="mt-1 rounded-lg border border-slate-200 bg-white px-3 py-3 text-base text-slate-900"
        />
        <TextInput
          value={dni}
          onChangeText={setDni}
          placeholder="DNI/NIE (opcional)"
          className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-3 text-base text-slate-900"
        />

        <View className="mt-4 gap-2">
          <Pressable
            onPress={() => setShowSignaturePad((v) => !v)}
            className="items-center rounded-lg bg-indigo-600 py-3 active:opacity-80"
          >
            <Text className="text-sm font-semibold text-white">
              {signatureDataUrl ? "Repetir firma" : "Capturar firma"}
            </Text>
          </Pressable>
          {signatureDataUrl ? <Text className="text-xs text-emerald-700">Firma capturada</Text> : null}
          {geostamp ? (
            <Text className="text-xs text-slate-600">
              Geostamp: {geostamp.lat.toFixed(5)}, {geostamp.lng.toFixed(5)}
            </Text>
          ) : null}
        </View>

        {showSignaturePad ? (
          <View className="mt-3 h-56 overflow-hidden rounded-lg border border-slate-200">
            <SignatureScreen
              onOK={onSignatureOK}
              onEmpty={() => setError("Firma vacía.")}
              descriptionText="Firma del receptor"
              clearText="Limpiar"
              confirmText="Guardar"
              webStyle={".m-signature-pad--footer { display: flex; }"}
            />
          </View>
        ) : null}

        <View className="mt-4 gap-2">
          <Pressable
            onPress={() => setShowCamera((v) => !v)}
            className="items-center rounded-lg bg-slate-900 py-3 active:opacity-80"
          >
            <Text className="text-sm font-semibold text-white">
              {photoUri ? "Repetir foto albarán" : "Abrir cámara"}
            </Text>
          </Pressable>
          {photoUri ? (
            <Image source={{ uri: photoUri }} style={{ height: 160, borderRadius: 8 }} resizeMode="cover" />
          ) : null}
        </View>

        {showCamera ? (
          <View className="mt-3 overflow-hidden rounded-lg border border-slate-200">
            <CameraView ref={cameraRef} style={{ height: 240 }} facing="back" />
            <Pressable onPress={() => void capturePhoto()} className="m-3 items-center rounded-lg bg-indigo-600 py-3">
              <Text className="text-sm font-semibold text-white">Tomar foto</Text>
            </Pressable>
          </View>
        ) : null}

        {error ? (
          <View className="mt-4 rounded-lg bg-red-50 px-3 py-2">
            <Text className="text-sm text-red-800">{error}</Text>
          </View>
        ) : null}
        {success ? (
          <View className="mt-4 rounded-lg bg-emerald-50 px-3 py-2">
            <Text className="text-sm text-emerald-800">{success}</Text>
          </View>
        ) : null}

        <Pressable
          disabled={saving}
          onPress={() => void onSubmit()}
          className="mt-5 items-center rounded-xl bg-emerald-600 py-3.5 active:opacity-90 disabled:opacity-50"
        >
          {saving ? <ActivityIndicator color="#fff" /> : <Text className="text-base font-semibold text-white">Registrar Entrega</Text>}
        </Pressable>
      </View>
    </ScrollView>
  );
}
