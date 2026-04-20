import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";

import { ApiError } from "../lib/api";
import type { GastoCreateInput, GastoRecent } from "../types/gasto";
import type { PodRegisterInput, PodRegisterResult } from "../types/porte";
import { createGastoOnline } from "./gastosApi";
import { registerPODOnline } from "./portesApi";

/** Máximo de reintentos automáticos por ítem; al superarlo pasa a la DLQ local (no se pierde el payload). */
export const MAX_TRIES = 3;

export const SYNC_QUEUE_KEY = "abl_sync_queue_v2";
/** Cola muerta local: ítems que agotaron reintentos o se movieron explícitamente desde «Limpiar errores». */
export const SYNC_DLQ_KEY = "abl_sync_dlq_v1";

export type SyncItemType = "POD" | "GASTO";

export type SyncQueueItem =
  | {
      id: string;
      type: "POD";
      createdAt: string;
      tries: number;
      lastError?: string;
      payload: PodRegisterInput;
    }
  | {
      id: string;
      type: "GASTO";
      createdAt: string;
      tries: number;
      lastError?: string;
      payload: GastoCreateInput;
    };

export type DeadLetterSyncItem = SyncQueueItem & {
  deadletteredAt: string;
};

export type SyncQueueState = {
  size: number;
  dlqSize: number;
  syncing: boolean;
  items: SyncQueueItem[];
  dlqItems: DeadLetterSyncItem[];
};

type QueueListener = (state: SyncQueueState) => void;

const listeners = new Set<QueueListener>();
let queueCache: SyncQueueItem[] | null = null;
let dlqCache: DeadLetterSyncItem[] | null = null;
let isSyncing = false;
let netInfoSubscribed = false;
let queueMutex: Promise<void> = Promise.resolve();

async function withQueueLock<T>(fn: () => Promise<T>): Promise<T> {
  const prev = queueMutex;
  let release: () => void = () => {};
  queueMutex = new Promise<void>((resolve) => {
    release = resolve;
  });
  await prev;
  try {
    return await fn();
  } finally {
    release();
  }
}

function notify() {
  const items = queueCache ?? [];
  const dlqItems = dlqCache ?? [];
  const snapshot: SyncQueueState = {
    size: items.length,
    dlqSize: dlqItems.length,
    syncing: isSyncing,
    items,
    dlqItems,
  };
  for (const cb of listeners) cb(snapshot);
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) return `HTTP ${error.status}`;
  if (error instanceof Error) return error.message;
  return "unknown_error";
}

function isLikelyNetworkError(error: unknown): boolean {
  if (error instanceof ApiError) return false;
  if (error instanceof TypeError) return true;
  if (error instanceof Error) {
    const m = error.message.toLowerCase();
    return (
      m.includes("network") ||
      m.includes("fetch") ||
      m.includes("timed out") ||
      m.includes("connection") ||
      m.includes("offline") ||
      m.includes("socket")
    );
  }
  return false;
}

function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && [401, 403].includes(error.status);
}

function stampDeadLetter(item: SyncQueueItem): DeadLetterSyncItem {
  return {
    ...item,
    deadletteredAt: new Date().toISOString(),
  };
}

function stripDeadLetterMeta(item: DeadLetterSyncItem): SyncQueueItem {
  const { deadletteredAt: _d, ...rest } = item;
  return rest as SyncQueueItem;
}

async function executeOnline(item: SyncQueueItem): Promise<void> {
  if (item.type === "POD") {
    await registerPODOnline(item.payload);
    return;
  }
  await createGastoOnline(item.payload);
}

async function readQueueFromStorage(): Promise<SyncQueueItem[]> {
  const raw = await AsyncStorage.getItem(SYNC_QUEUE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as SyncQueueItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function readDlqFromStorage(): Promise<DeadLetterSyncItem[]> {
  const raw = await AsyncStorage.getItem(SYNC_DLQ_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as DeadLetterSyncItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((row) => row && typeof row.id === "string" && typeof row.deadletteredAt === "string");
  } catch {
    return [];
  }
}

async function loadQueue(): Promise<SyncQueueItem[]> {
  if (queueCache) return queueCache;
  const q = await readQueueFromStorage();
  queueCache = q;
  return queueCache;
}

async function loadDlq(): Promise<DeadLetterSyncItem[]> {
  if (dlqCache) return dlqCache;
  const q = await readDlqFromStorage();
  dlqCache = q;
  return dlqCache;
}

async function saveQueue(queue: SyncQueueItem[]) {
  queueCache = queue;
  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
  notify();
}

async function saveDlq(queue: DeadLetterSyncItem[]) {
  dlqCache = queue;
  await AsyncStorage.setItem(SYNC_DLQ_KEY, JSON.stringify(queue));
  notify();
}

async function enqueue(item: SyncQueueItem): Promise<void> {
  await withQueueLock(async () => {
    const q = await readQueueFromStorage();
    queueCache = q;
    q.push(item);
    await saveQueue(q);
  });
}

export function subscribeSyncStatus(listener: QueueListener): () => void {
  listeners.add(listener);
  listener({
    size: queueCache?.length ?? 0,
    dlqSize: dlqCache?.length ?? 0,
    syncing: isSyncing,
    items: queueCache ?? [],
    dlqItems: dlqCache ?? [],
  });
  return () => listeners.delete(listener);
}

export async function getPendingSyncCount(): Promise<number> {
  const q = await loadQueue();
  return q.length;
}

export async function getDlqCount(): Promise<number> {
  const d = await loadDlq();
  return d.length;
}

export async function getPendingSyncItems(): Promise<SyncQueueItem[]> {
  return [...(await loadQueue())];
}

export async function getDlqItems(): Promise<DeadLetterSyncItem[]> {
  return [...(await loadDlq())];
}

/**
 * Mueve a la DLQ los ítems con intentos agotados (no los borra).
 * Los ítems recuperables permanecen en la cola activa.
 */
export async function clearSyncErrors(): Promise<void> {
  await withQueueLock(async () => {
    const q = await readQueueFromStorage();
    queueCache = q;
    const exhausted = q.filter((i) => i.tries >= MAX_TRIES);
    const alive = q.filter((i) => i.tries < MAX_TRIES);
    if (exhausted.length) {
      await appendToDlqInner(exhausted.map(stampDeadLetter));
    }
    await saveQueue(alive);
  });
}

async function appendToDlqInner(items: DeadLetterSyncItem[]): Promise<void> {
  if (!items.length) return;
  const cur = await readDlqFromStorage();
  const seen = new Set(cur.map((i) => i.id));
  const merged = [...cur];
  for (const it of items) {
    if (!seen.has(it.id)) {
      merged.push(it);
      seen.add(it.id);
    }
  }
  dlqCache = merged;
  await AsyncStorage.setItem(SYNC_DLQ_KEY, JSON.stringify(merged));
}

/** Migra en caliente ítems ya agotados que siguieran en la cola legacy. */
export async function migrateExhaustedToDlq(): Promise<void> {
  await withQueueLock(async () => {
    const q = await readQueueFromStorage();
    queueCache = q;
    const exhausted = q.filter((i) => i.tries >= MAX_TRIES);
    const alive = q.filter((i) => i.tries < MAX_TRIES);
    if (!exhausted.length) {
      queueCache = alive;
      return;
    }
    await appendToDlqInner(exhausted.map(stampDeadLetter));
    await saveQueue(alive);
  });
}

export async function retrySyncItem(itemId: string): Promise<void> {
  const q = await loadQueue();
  const idx = q.findIndex((x) => x.id === itemId);
  if (idx < 0) return;
  const item = q[idx];
  try {
    await executeOnline(item);
    await withQueueLock(async () => {
      const latest = await readQueueFromStorage();
      queueCache = latest;
      const j = latest.findIndex((x) => x.id === itemId);
      if (j >= 0) {
        latest.splice(j, 1);
        await saveQueue(latest);
      }
    });
  } catch (error) {
    await withQueueLock(async () => {
      const latest = await readQueueFromStorage();
      queueCache = latest;
      const j = latest.findIndex((x) => x.id === itemId);
      if (j < 0) return;
      const tries = latest[j].tries + 1;
      const lastError = describeError(error);
      if (tries >= MAX_TRIES) {
        const [removed] = latest.splice(j, 1);
        await saveQueue(latest);
        await appendToDlqInner([stampDeadLetter({ ...removed, tries, lastError } as SyncQueueItem)]);
        notify();
        return;
      }
      latest[j] = {
        ...latest[j],
        tries,
        lastError,
      } as SyncQueueItem;
      await saveQueue(latest);
    });
  }
}

/** Vuelve a poner un ítem de la DLQ al final de la cola activa (intentos a cero). */
export async function reenqueueFromDlq(itemId: string): Promise<void> {
  await withQueueLock(async () => {
    const dlq = await readDlqFromStorage();
    dlqCache = dlq;
    const di = dlq.findIndex((x) => x.id === itemId);
    if (di < 0) return;
    const [raw] = dlq.splice(di, 1);
    const base = stripDeadLetterMeta(raw);
    const revived: SyncQueueItem = {
      ...base,
      tries: 0,
      lastError: undefined,
    } as SyncQueueItem;
    const q = await readQueueFromStorage();
    queueCache = q;
    q.push(revived);
    dlqCache = dlq;
    await AsyncStorage.setItem(SYNC_DLQ_KEY, JSON.stringify(dlq));
    await saveQueue(q);
  });
}

/** Elimina un registro de la DLQ (p. ej. duplicado irrecuperable). */
export async function removeDeadLetter(itemId: string): Promise<void> {
  await withQueueLock(async () => {
    const dlq = await readDlqFromStorage();
    const next = dlq.filter((x) => x.id !== itemId);
    await saveDlq(next);
  });
}

export async function processPendingSyncQueue(): Promise<void> {
  if (isSyncing) return;
  isSyncing = true;
  notify();
  try {
    const state = await NetInfo.fetch();
    if (!state.isConnected) return;

    const queue = await loadQueue();
    if (queue.length === 0) return;
    const snapshotIds = new Set(queue.map((q) => q.id));

    const remaining: SyncQueueItem[] = [];
    const dlqBatch: DeadLetterSyncItem[] = [];
    for (let i = 0; i < queue.length; i += 1) {
      const item = queue[i];
      if (item.tries >= MAX_TRIES) {
        console.warn(
          "[sync_service] Ítem movido a DLQ por exceder reintentos",
          JSON.stringify({
            id: item.id,
            type: item.type,
            tries: item.tries,
            maxTries: MAX_TRIES,
            lastError: item.lastError,
          }),
        );
        dlqBatch.push(stampDeadLetter(item));
        continue;
      }
      try {
        await executeOnline(item);
      } catch (error) {
        const rest = queue.slice(i + 1);
        if (isAuthError(error)) {
          remaining.push({ ...item, lastError: describeError(error) }, ...rest);
          break;
        }
        if (isLikelyNetworkError(error)) {
          remaining.push(
            {
              ...item,
              tries: item.tries + 1,
              lastError: describeError(error),
            },
            ...rest,
          );
          break;
        }
      }
    }
    await withQueueLock(async () => {
      if (dlqBatch.length) {
        await appendToDlqInner(dlqBatch);
      }
      const latest = await readQueueFromStorage();
      queueCache = latest;
      const newlyAdded = latest.filter((q) => !snapshotIds.has(q.id));
      await saveQueue([...remaining, ...newlyAdded]);
    });
  } finally {
    isSyncing = false;
    notify();
  }
}

export async function registerPOD(input: PodRegisterInput): Promise<PodRegisterResult> {
  try {
    return await registerPODOnline(input);
  } catch (error) {
    if (!isLikelyNetworkError(error)) throw error;
    await enqueue({
      id: `pod-${input.porteId}-${Date.now()}`,
      type: "POD",
      createdAt: new Date().toISOString(),
      tries: 0,
      payload: input,
      lastError: describeError(error),
    });
    return { estado: "pendiente_sync", mode: "queued_offline" };
  }
}

export async function saveGasto(input: GastoCreateInput): Promise<GastoRecent | null> {
  try {
    return await createGastoOnline(input);
  } catch (error) {
    if (!isLikelyNetworkError(error)) throw error;
    await enqueue({
      id: `gasto-${Date.now()}`,
      type: "GASTO",
      createdAt: new Date().toISOString(),
      tries: 0,
      payload: input,
      lastError: describeError(error),
    });
    return null;
  }
}

export function initSyncBackgroundWorker(): void {
  if (netInfoSubscribed) return;
  netInfoSubscribed = true;
  void (async () => {
    await migrateExhaustedToDlq();
    await loadQueue();
    await loadDlq();
    notify();
  })();
  void processPendingSyncQueue();
  NetInfo.addEventListener((state) => {
    void (async () => {
      await migrateExhaustedToDlq();
      await loadQueue();
      await loadDlq();
      notify();
      if (state.isConnected) void processPendingSyncQueue();
    })();
  });
}
