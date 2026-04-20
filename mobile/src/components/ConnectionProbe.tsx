import { useCallback, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { fetchLiveProbe } from "../lib/api";
import { getApiBaseUrl } from "../lib/config";

/**
 * Prueba de conectividad contra `GET /live` (sin autenticación).
 */
export function ConnectionProbe() {
  const [loading, setLoading] = useState(false);
  const [last, setLast] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setLast(null);
    try {
      const r = await fetchLiveProbe();
      setLast(`${r.ok ? "OK" : "FAIL"} ${r.status} — ${r.snippet}`);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <View className="rounded-xl border border-slate-200 bg-white p-4">
      <Text className="text-sm font-semibold text-slate-800">Prueba de conexión</Text>
      <Text className="mt-1 text-xs text-slate-500" numberOfLines={2}>
        Base: {getApiBaseUrl()}
      </Text>
      <Pressable
        onPress={run}
        disabled={loading}
        className="mt-3 items-center rounded-lg bg-slate-900 py-2 active:opacity-80"
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text className="text-sm font-medium text-white">Ping GET /live</Text>
        )}
      </Pressable>
      {last ? <Text className="mt-2 text-xs text-slate-600">{last}</Text> : null}
    </View>
  );
}
