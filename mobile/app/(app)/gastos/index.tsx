import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import { ApiError } from "../../../src/lib/api";
import { fetchRecentGastos } from "../../../src/services/gastosApi";
import type { GastoRecent } from "../../../src/types/gasto";

function fmtDetail(error: unknown): string {
  if (error instanceof ApiError) return typeof error.body === "string" ? error.body : JSON.stringify(error.body);
  if (error instanceof Error) return error.message;
  return "Error al cargar gastos";
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
      setError(fmtDetail(e));
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
    <View className="flex-1 bg-slate-50">
      <View className="flex-row items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <Text className="text-lg font-semibold text-slate-900">Gastos recientes</Text>
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
          ListEmptyComponent={<Text className="py-10 text-center text-slate-500">No hay gastos registrados.</Text>}
          ListHeaderComponent={
            error ? (
              <View className="mb-2 rounded-lg bg-amber-50 px-3 py-2">
                <Text className="text-sm text-amber-900">{error}</Text>
              </View>
            ) : null
          }
          renderItem={({ item }) => (
            <View className="rounded-xl border border-slate-200 bg-white p-4">
              <Text className="text-xs uppercase text-slate-500">{item.fecha}</Text>
              <Text className="mt-1 text-base font-semibold text-slate-900">{item.proveedor}</Text>
              <Text className="mt-1 text-sm text-slate-600">
                {item.categoria} · {item.total_chf} {item.moneda}
              </Text>
              {item.porte_id ? <Text className="mt-1 text-xs text-indigo-700">Porte vinculado: {item.porte_id}</Text> : null}
            </View>
          )}
        />
      )}
    </View>
  );
}
