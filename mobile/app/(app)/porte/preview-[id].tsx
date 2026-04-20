import { useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Text, View } from "react-native";
import { WebView } from "react-native-webview";

import { getMemoryAccessToken } from "../../../src/lib/api";
import { getApiBaseUrl } from "../../../src/lib/config";

export default function PortePodPdfPreviewScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const porteId = String(id || "").trim();
  const token = getMemoryAccessToken();

  if (!porteId) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50 px-5">
        <Text className="text-center text-slate-700">ID de porte inválido.</Text>
      </View>
    );
  }

  const uri = `${getApiBaseUrl()}/api/v1/portes/${porteId}/albaran-entrega`;
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  return (
    <View className="flex-1 bg-slate-50">
      <WebView
        source={{ uri, headers }}
        startInLoadingState
        renderLoading={() => (
          <View className="flex-1 items-center justify-center bg-slate-50">
            <ActivityIndicator size="large" />
            <Text className="mt-2 text-xs text-slate-500">Cargando albarán PDF...</Text>
          </View>
        )}
      />
    </View>
  );
}
