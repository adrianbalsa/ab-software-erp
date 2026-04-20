import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import {
  clearSyncErrors,
  getPendingSyncItems,
  processPendingSyncQueue,
  retrySyncItem,
  type SyncQueueItem,
} from "../../src/services/sync_service";

export default function PendientesScreen() {
  const [items, setItems] = useState<SyncQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyItem, setBusyItem] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const out = await getPendingSyncItems();
    setItems(out);
    setLoading(false);
  }, []);

  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const retryOne = async (id: string) => {
    setBusyItem(id);
    try {
      await retrySyncItem(id);
      await refresh();
    } finally {
      setBusyItem(null);
    }
  };

  const retryAll = async () => {
    setBusyItem("__all__");
    try {
      await processPendingSyncQueue();
      await refresh();
    } finally {
      setBusyItem(null);
    }
  };

  const clearErrors = async () => {
    setBusyItem("__clear__");
    try {
      await clearSyncErrors();
      await refresh();
    } finally {
      setBusyItem(null);
    }
  };

  return (
    <View className="flex-1 bg-slate-50">
      <View className="border-b border-slate-200 bg-white px-4 py-3">
        <Text className="text-lg font-semibold text-slate-900">Sincronización pendiente</Text>
        <View className="mt-2 flex-row gap-2">
          <Pressable onPress={() => void retryAll()} className="rounded-lg bg-indigo-600 px-3 py-2">
            <Text className="text-xs font-semibold text-white">{busyItem === "__all__" ? "Reintentando..." : "Forzar reintento global"}</Text>
          </Pressable>
          <Pressable onPress={() => void clearErrors()} className="rounded-lg bg-slate-700 px-3 py-2">
            <Text className="text-xs font-semibold text-white">{busyItem === "__clear__" ? "Limpiando..." : "Limpiar errores"}</Text>
          </Pressable>
        </View>
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
          ListEmptyComponent={<Text className="py-10 text-center text-slate-500">No hay pendientes en cola.</Text>}
          renderItem={({ item }) => (
            <View className="rounded-xl border border-slate-200 bg-white p-4">
              <Text className="text-xs uppercase text-slate-500">{item.type}</Text>
              <Text className="mt-1 text-sm text-slate-800">Creado: {item.createdAt}</Text>
              <Text className="text-sm text-slate-800">Intentos: {item.tries}</Text>
              {item.lastError ? <Text className="mt-1 text-xs text-amber-700">Último error: {item.lastError}</Text> : null}
              <Pressable
                onPress={() => void retryOne(item.id)}
                disabled={busyItem === item.id}
                className="mt-3 self-start rounded-lg bg-emerald-600 px-3 py-2 disabled:opacity-50"
              >
                <Text className="text-xs font-semibold text-white">{busyItem === item.id ? "Reintentando..." : "Forzar Reintento"}</Text>
              </Pressable>
            </View>
          )}
        />
      )}
    </View>
  );
}
