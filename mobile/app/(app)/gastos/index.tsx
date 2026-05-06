import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import { ApiError } from "../../../src/lib/api";
import { userFacingFetchFailureMessage } from "../../../src/lib/networkMessages";
import { fetchRecentGastos } from "../../../src/services/gastosApi";
import type { GastoRecent } from "../../../src/types/gasto";

function formatLoadError(error: unknown): string {
  if (error instanceof ApiError) return typeof error.body === "string" ? error.body : JSON.stringify(error.body);
  return userFacingFetchFailureMessage(error);
}

export default function GastosScreen() {
  const router = useRouter();
  const [items, setItems] = useState<GastoRecent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const out = await fetchRecentGastos();
      setItems(out);
    } catch (e) {
      setError(formatLoadError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  return (
    <View className="flex-1 bg-slate-50 dark:bg-zinc-950">
      <View className="flex-row items-center justify-between border-b border-slate-200 bg-white dark:border-zinc-700 dark:bg-zinc-900 px-4 py-3">
        <Text className="text-lg font-semibold text-slate-900 dark:text-zinc-100">Gastos recientes</Text>
        <Pressable onPress={() => router.push("/(app)/gastos/nuevo")} className="rounded-lg bg-indigo-600 px-3 py-2">
          <Text className="text-sm font-semibold text-white">Nuevo</Text>
        </Pressable>
      </View>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          ListEmptyComponent={<Text className="py-10 text-center text-slate-500 dark:text-zinc-500">No hay gastos registrados.</Text>}
          ListHeaderComponent={
            error ? (
              <View className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-900/50 dark:bg-amber-950/35">
                <Text className="text-sm text-amber-950 dark:text-amber-100">{error}</Text>
              </View>
            ) : null
          }
          renderItem={({ item }) => (
            <View className="rounded-xl border border-slate-200 bg-white dark:border-zinc-700 dark:bg-zinc-900 p-4">
              <Text className="text-xs uppercase text-slate-500 dark:text-zinc-500">{item.fecha}</Text>
              <Text className="mt-1 text-base font-semibold text-slate-900 dark:text-zinc-100">{item.proveedor}</Text>
              <Text className="mt-1 text-sm text-slate-600 dark:text-zinc-400">
                {item.categoria} · {item.total_chf} {item.moneda}
              </Text>
              {item.porte_id ? (
                <Text className="mt-1 text-xs text-indigo-700 dark:text-indigo-400">Porte vinculado: {item.porte_id}</Text>
              ) : null}
            </View>
          )}
        />
      )}
    </View>
  );
}
