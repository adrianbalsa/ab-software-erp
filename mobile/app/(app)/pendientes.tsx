import { useFocusEffect } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import {
  clearSyncErrors,
  getDlqItems,
  getPendingSyncItems,
  MAX_TRIES,
  processPendingSyncQueue,
  reenqueueFromDlq,
  removeDeadLetter,
  retrySyncItem,
  type DeadLetterSyncItem,
  type SyncQueueItem,
} from "../../src/services/sync_service";

type Row =
  | { key: string; kind: "header-active" }
  | { key: string; kind: "header-dlq" }
  | { key: string; kind: "item"; item: SyncQueueItem }
  | { key: string; kind: "dlq"; item: DeadLetterSyncItem };

export default function PendientesScreen() {
  const [items, setItems] = useState<SyncQueueItem[]>([]);
  const [dlq, setDlq] = useState<DeadLetterSyncItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyItem, setBusyItem] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [out, dead] = await Promise.all([getPendingSyncItems(), getDlqItems()]);
    setItems(out);
    setDlq(dead);
    setLoading(false);
  }, []);

  const rows = useMemo((): Row[] => {
    const r: Row[] = [{ key: "h-active", kind: "header-active" }, ...items.map((i) => ({ key: i.id, kind: "item" as const, item: i }))];
    if (dlq.length > 0) {
      r.push({ key: "h-dlq", kind: "header-dlq" });
      r.push(...dlq.map((i) => ({ key: `dlq-${i.id}`, kind: "dlq" as const, item: i })));
    }
    return r;
  }, [items, dlq]);

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

  const reviveOne = async (id: string) => {
    setBusyItem(`dlq:${id}`);
    try {
      await reenqueueFromDlq(id);
      await refresh();
    } finally {
      setBusyItem(null);
    }
  };

  const discardDlq = async (id: string) => {
    setBusyItem(`rm:${id}`);
    try {
      await removeDeadLetter(id);
      await refresh();
    } finally {
      setBusyItem(null);
    }
  };

  return (
    <View className="flex-1 bg-slate-50">
      <View className="border-b border-slate-200 bg-white px-4 py-3">
        <Text className="text-lg font-semibold text-slate-900">Sincronización pendiente</Text>
        <View className="mt-2 flex-row flex-wrap gap-2">
          <Pressable onPress={() => void retryAll()} className="rounded-lg bg-indigo-600 px-3 py-2">
            <Text className="text-xs font-semibold text-white">{busyItem === "__all__" ? "Reintentando..." : "Forzar reintento global"}</Text>
          </Pressable>
          <Pressable onPress={() => void clearErrors()} className="rounded-lg bg-slate-700 px-3 py-2">
            <Text className="text-xs font-semibold text-white">{busyItem === "__clear__" ? "Moviendo..." : "Mover agotados a DLQ"}</Text>
          </Pressable>
        </View>
        <Text className="mt-2 text-xs text-slate-500">
          Cola activa: reintentos automáticos. DLQ: más de {MAX_TRIES} intentos fallidos; reencolar o descartar.
        </Text>
      </View>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" />
        </View>
      ) : items.length === 0 && dlq.length === 0 ? (
        <Text className="py-10 text-center text-slate-500">No hay pendientes ni registros en DLQ.</Text>
      ) : (
        <FlatList
          data={rows}
          keyExtractor={(r) => r.key}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          renderItem={({ item: row }) => {
            if (row.kind === "header-active") {
              return (
                <Text className="pt-2 text-sm font-semibold uppercase tracking-wide text-slate-600">
                  Cola activa ({items.length})
                </Text>
              );
            }
            if (row.kind === "header-dlq") {
              return (
                <Text className="pt-4 text-sm font-semibold uppercase tracking-wide text-rose-700">
                  Cola muerta — DLQ ({dlq.length})
                </Text>
              );
            }
            if (row.kind === "item") {
              const item = row.item;
              return (
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
                    <Text className="text-xs font-semibold text-white">{busyItem === item.id ? "Reintentando..." : "Forzar reintento"}</Text>
                  </Pressable>
                </View>
              );
            }
            const d = row.item;
            return (
              <View className="rounded-xl border border-rose-200 bg-rose-50/80 p-4">
                <Text className="text-xs font-semibold uppercase text-rose-800">{d.type} · DLQ</Text>
                <Text className="mt-1 text-xs text-rose-900">En DLQ: {d.deadletteredAt}</Text>
                <Text className="mt-1 text-sm text-rose-950">Intentos finales: {d.tries}</Text>
                {d.lastError ? <Text className="mt-1 text-xs text-rose-800">Error: {d.lastError}</Text> : null}
                <View className="mt-3 flex-row flex-wrap gap-2">
                  <Pressable
                    onPress={() => void reviveOne(d.id)}
                    disabled={busyItem === `dlq:${d.id}`}
                    className="rounded-lg bg-indigo-600 px-3 py-2 disabled:opacity-50"
                  >
                    <Text className="text-xs font-semibold text-white">{busyItem === `dlq:${d.id}` ? "…" : "Reencolar"}</Text>
                  </Pressable>
                  <Pressable
                    onPress={() => void discardDlq(d.id)}
                    disabled={busyItem === `rm:${d.id}`}
                    className="rounded-lg border border-rose-400 bg-white px-3 py-2 disabled:opacity-50"
                  >
                    <Text className="text-xs font-semibold text-rose-900">{busyItem === `rm:${d.id}` ? "…" : "Descartar"}</Text>
                  </Pressable>
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}
