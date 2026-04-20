import { useCallback, useEffect, useState } from "react";
import { useRouter } from "expo-router";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  View,
} from "react-native";

import { ConnectionProbe } from "../../src/components/ConnectionProbe";
import { useAuth } from "../../src/context/AuthContext";
import { ApiError } from "../../src/lib/api";
import { fetchRecentGastos } from "../../src/services/gastosApi";
import { fetchPortesPendientes } from "../../src/services/portesApi";
import {
  getDlqCount,
  getPendingSyncCount,
  processPendingSyncQueue,
  subscribeSyncStatus,
} from "../../src/services/sync_service";
import type { PorteListItem } from "../../src/types/porte";

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail === null || detail === undefined) return "Error";
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function PortesScreen() {
  const { signOut } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<PorteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queueSize, setQueueSize] = useState(0);
  const [dlqSize, setDlqSize] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [kmMes, setKmMes] = useState<number>(0);
  const [gastoSemana, setGastoSemana] = useState<number>(0);

  const load = useCallback(async () => {
    setError(null);
    try {
      const rows = await fetchPortesPendientes();
      setItems(rows);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(formatDetail(e.body));
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("No se pudieron cargar los portes");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let active = true;
    void Promise.all([getPendingSyncCount(), getDlqCount()]).then(([n, d]) => {
      if (active) {
        setQueueSize(n);
        setDlqSize(d);
      }
    });
    const unsub = subscribeSyncStatus(({ size, dlqSize: dsz, syncing }) => {
      setQueueSize(size);
      setDlqSize(dsz);
      setIsSyncing(syncing);
    });
    void processPendingSyncQueue();
    void fetchPersonalSummary();
    return () => {
      active = false;
      unsub();
    };
  }, []);

  const fetchPersonalSummary = useCallback(async () => {
    try {
      const [portes, gastos] = await Promise.all([fetchPortesPendientes(), fetchRecentGastos()]);
      const now = new Date();
      const month = now.getMonth();
      const year = now.getFullYear();
      const weekAgo = new Date(now);
      weekAgo.setDate(now.getDate() - 7);

      const km = portes.reduce((acc, p) => {
        const d = new Date(p.fecha);
        if (d.getFullYear() === year && d.getMonth() === month) return acc + Number(p.km_estimados || 0);
        return acc;
      }, 0);

      const weekly = gastos.reduce((acc, g) => {
        const d = new Date(g.fecha);
        if (d >= weekAgo) return acc + Number(g.total_chf || 0);
        return acc;
      }, 0);

      setKmMes(Math.round(km * 10) / 10);
      setGastoSemana(Math.round(weekly * 100) / 100);
    } catch {
      // Widget informativo, no bloqueante.
    }
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    void load();
  };

  if (loading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" />
        <Text className="mt-2 text-sm text-slate-500">Cargando portes…</Text>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-slate-50">
      <View className="flex-row items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <Text className="text-lg font-semibold text-slate-900">Portes pendientes</Text>
        <View className="flex-row gap-2">
          <Pressable onPress={() => router.push("/(app)/pendientes")} className="rounded-lg bg-slate-700 px-3 py-1.5 active:opacity-80">
            <Text className="text-sm font-medium text-white">Pendientes</Text>
          </Pressable>
          <Pressable onPress={() => router.push("/(app)/gastos")} className="rounded-lg bg-indigo-600 px-3 py-1.5 active:opacity-80">
            <Text className="text-sm font-medium text-white">Gastos</Text>
          </Pressable>
          <Pressable onPress={() => void signOut()} className="rounded-lg bg-slate-200 px-3 py-1.5 active:opacity-80">
            <Text className="text-sm font-medium text-slate-800">Salir</Text>
          </Pressable>
        </View>
      </View>

      {error ? (
        <View className="mx-4 mt-3 rounded-lg bg-amber-50 px-3 py-2">
          <Text className="text-sm text-amber-900">{error}</Text>
          <Pressable onPress={() => void load()} className="mt-2 self-start">
            <Text className="text-sm font-medium text-amber-950 underline">Reintentar</Text>
          </Pressable>
        </View>
      ) : null}

      <View className="mx-4 mt-3 rounded-lg border border-slate-200 bg-white px-3 py-3">
        <Text className="text-xs uppercase text-slate-500">Resumen personal</Text>
        <Text className="mt-1 text-sm text-slate-800">Km realizados (mes): {kmMes}</Text>
        <Text className="text-sm text-slate-800">Total gastos registrados (semana): {gastoSemana} EUR</Text>
      </View>

      {queueSize > 0 || dlqSize > 0 ? (
        <View className="mx-4 mt-3 rounded-lg bg-indigo-50 px-3 py-2">
          {queueSize > 0 ? (
            <Text className="text-xs text-indigo-900">
              Sincronizando ítems pendientes… ({queueSize}) {isSyncing ? "en curso" : "en cola"}
            </Text>
          ) : null}
          {dlqSize > 0 ? (
            <Text className={`text-xs text-rose-800 ${queueSize > 0 ? "mt-1" : ""}`}>
              DLQ local: {dlqSize} {dlqSize === 1 ? "ítem" : "ítems"} atascado{dlqSize === 1 ? "" : "s"} — abre Pendientes para reencolar o descartar.
            </Text>
          ) : null}
        </View>
      ) : null}

      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 24 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListHeaderComponent={
          <View className="mb-4">
            <ConnectionProbe />
          </View>
        }
        ListEmptyComponent={
          <Text className="py-8 text-center text-slate-500">No hay portes pendientes.</Text>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push(`/(app)/porte/${item.id}`)}
            className="mb-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm active:opacity-80"
          >
            <Text className="text-xs font-medium uppercase text-slate-400">{item.fecha}</Text>
            <Text className="mt-1 text-base font-semibold text-slate-900" numberOfLines={1}>
              {item.origen} → {item.destino}
            </Text>
            <View className="mt-2 flex-row flex-wrap gap-2">
              <View className="rounded-md bg-slate-100 px-2 py-1">
                <Text className="text-xs text-slate-700">{item.estado}</Text>
              </View>
              <View className="rounded-md bg-slate-100 px-2 py-1">
                <Text className="text-xs text-slate-700">{item.km_estimados} km</Text>
              </View>
              {item.precio_pactado != null ? (
                <View className="rounded-md bg-emerald-50 px-2 py-1">
                  <Text className="text-xs font-medium text-emerald-900">{item.precio_pactado} €</Text>
                </View>
              ) : null}
            </View>
            {item.descripcion ? (
              <Text className="mt-2 text-sm text-slate-600" numberOfLines={2}>
                {item.descripcion}
              </Text>
            ) : null}
            <Text className="mt-3 text-xs font-medium text-indigo-700">Ver detalle y registrar entrega</Text>
          </Pressable>
        )}
      />
    </View>
  );
}
