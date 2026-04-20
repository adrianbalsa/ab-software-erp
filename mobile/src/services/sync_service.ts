import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";

import { ApiError } from "../lib/api";
import type { GastoCreateInput, GastoRecent } from "../types/gasto";
import type { PodRegisterInput, PodRegisterResult } from "../types/porte";
import { createGastoOnline } from "./gastosApi";
import { registerPODOnline } from "./portesApi";

export const SYNC_QUEUE_KEY = "abl_sync_queue_v2";

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

type QueueListener = (state: { size: number; syncing: boolean; items: SyncQueueItem[] }) => void;

const listeners = new Set<QueueListener>();
let queueCache: SyncQueueItem[] | null = null;
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
  const snapshot = queueCache ?? [];
  for (const cb of listeners) cb({ size: snapshot.length, syncing: isSyncing, items: snapshot });
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

async function executeOnline(item: SyncQueueItem): Promise<void> {
  if (item.type === "POD") {
    await registerPODOnline(item.payload);
    return;
  }
  await createGastoOnline(item.payload);
}

async function loadQueue(): Promise<SyncQueueItem[]> {
  if (queueCache) return queueCache;
  const raw = await AsyncStorage.getItem(SYNC_QUEUE_KEY);
  if (!raw) {
    queueCache = [];
    return queueCache;
  }
  try {
    const parsed = JSON.parse(raw) as SyncQueueItem[];
    queueCache = Array.isArray(parsed) ? parsed : [];
  } catch {
    queueCache = [];
  }
  return queueCache;
}

async function saveQueue(queue: SyncQueueItem[]) {
  queueCache = queue;
  await AsyncStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
  notify();
}

async function enqueue(item: SyncQueueItem): Promise<void> {
  await withQueueLock(async () => {
    const q = await loadQueue();
    q.push(item);
    await saveQueue(q);
  });
}

export function subscribeSyncStatus(listener: QueueListener): () => void {
  listeners.add(listener);
  listener({ size: queueCache?.length ?? 0, syncing: isSyncing, items: queueCache ?? [] });
  return () => listeners.delete(listener);
}

export async function getPendingSyncCount(): Promise<number> {
  const q = await loadQueue();
  return q.length;
}

export async function getPendingSyncItems(): Promise<SyncQueueItem[]> {
  return [...(await loadQueue())];
}

export async function clearSyncErrors(): Promise<void> {
  await withQueueLock(async () => {
    const q = await loadQueue();
    const cleaned = q.filter((i) => i.tries < 3);
    await saveQueue(cleaned);
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
      const latest = await loadQueue();
      const j = latest.findIndex((x) => x.id === itemId);
      if (j >= 0) {
        latest.splice(j, 1);
        await saveQueue(latest);
      }
    });
  } catch (error) {
    await withQueueLock(async () => {
      const latest = await loadQueue();
      const j = latest.findIndex((x) => x.id === itemId);
      if (j >= 0) {
        latest[j] = {
          ...latest[j],
          tries: latest[j].tries + 1,
          lastError: describeError(error),
        } as SyncQueueItem;
        await saveQueue(latest);
      }
    });
  }
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
    for (let i = 0; i < queue.length; i += 1) {
      const item = queue[i];
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
        // Error funcional: se descarta el item para no bloquear la cola.
      }
    }
    await withQueueLock(async () => {
      const latest = await loadQueue();
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
  void loadQueue().then(() => notify());
  void processPendingSyncQueue();
  NetInfo.addEventListener((state) => {
    if (state.isConnected) void processPendingSyncQueue();
  });
}
