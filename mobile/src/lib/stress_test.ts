import AsyncStorage from "@react-native-async-storage/async-storage";

import { SYNC_QUEUE_KEY, type SyncQueueItem } from "../services/sync_service";

function fakePodItem(idx: number): SyncQueueItem {
  return {
    id: `stress-pod-${idx}-${Date.now()}`,
    type: "POD",
    createdAt: new Date().toISOString(),
    tries: idx % 3,
    lastError: idx % 5 === 0 ? "simulated_network_error" : undefined,
    payload: {
      porteId: `00000000-0000-0000-0000-${String(idx).padStart(12, "0")}`,
      nombreConsignatario: `Receptor ${idx}`,
      dniConsignatario: `X${idx}Z`,
      signatureDataUrl:
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6YpXcAAAAASUVORK5CYII=",
      photoUri: `file:///tmp/stress_ticket_${idx}.jpg`,
      geostamp: {
        lat: 40.4168 + idx * 0.0001,
        lng: -3.7038 - idx * 0.0001,
        captured_at: new Date().toISOString(),
      },
    },
  };
}

function fakeGastoItem(idx: number): SyncQueueItem {
  const categorias = ["combustible", "materiales", "servicios", "otros"] as const;
  return {
    id: `stress-gasto-${idx}-${Date.now()}`,
    type: "GASTO",
    createdAt: new Date().toISOString(),
    tries: idx % 4,
    lastError: idx % 4 === 0 ? "simulated_timeout" : undefined,
    payload: {
      proveedor: `Proveedor Stress ${idx}`,
      fecha: new Date().toISOString().slice(0, 10),
      total_chf: Number((10 + idx * 1.37).toFixed(2)),
      categoria: categorias[idx % categorias.length],
      moneda: "EUR",
      concepto: `Ticket stress ${idx}`,
      nif_proveedor: `B12${String(idx).padStart(6, "0")}`,
      iva: Number((1.73 + idx * 0.07).toFixed(2)),
      total_eur: Number((10 + idx * 1.37).toFixed(2)),
      porte_id: `00000000-0000-0000-0000-${String(idx).padStart(12, "0")}`,
      ticketUri: `file:///tmp/stress_gasto_${idx}.jpg`,
    },
  };
}

/**
 * Inyecta 50 items en la cola offline:
 * - 25 POD
 * - 25 GASTO
 */
export async function injectOfflineStressQueue(): Promise<{ total: number; pod: number; gasto: number }> {
  const queue: SyncQueueItem[] = [];
  for (let i = 0; i < 25; i += 1) queue.push(fakePodItem(i + 1));
  for (let i = 0; i < 25; i += 1) queue.push(fakeGastoItem(i + 1));
  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
  return { total: queue.length, pod: 25, gasto: 25 };
}

export async function clearOfflineStressQueue(): Promise<void> {
  await AsyncStorage.removeItem(SYNC_QUEUE_KEY);
}
