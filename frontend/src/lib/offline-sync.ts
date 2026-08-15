"use client";

import { useEffect, useState } from "react";
import { openDB, type IDBPDatabase } from "idb";
import { submitAnswer, type SubmitPayload } from "./api";

const DB_NAME = "danyshpan-offline";
const DB_VERSION = 1;
const STORE_PENDING = "pending";
const STORE_SNAPSHOTS = "snapshots";

export type PendingStatus = "pending" | "syncing" | "failed";

export interface PendingAnswer {
  id?: number;
  created_at: number;
  session_id: string;
  payload: SubmitPayload;
  status: PendingStatus;
}

export interface SessionSnapshot {
  session_id: string;
  saved_at: number;
  question: {
    template_id: number;
    params: Record<string, unknown>;
    answer_type: string;
    time_limit_sec: number;
  } | null;
  mode: string;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_PENDING)) {
          const pending = db.createObjectStore(STORE_PENDING, {
            keyPath: "id",
            autoIncrement: true,
          });
          pending.createIndex("status", "status");
          pending.createIndex("created_at", "created_at");
        }
        if (!db.objectStoreNames.contains(STORE_SNAPSHOTS)) {
          db.createObjectStore(STORE_SNAPSHOTS, { keyPath: "session_id" });
        }
      },
    });
  }
  return dbPromise;
}

export async function saveOfflineAnswer(
  payload: SubmitPayload,
  status: PendingStatus = "pending",
): Promise<number> {
  const db = await getDb();
  const record: PendingAnswer = {
    created_at: Date.now(),
    session_id: payload.session_id,
    payload,
    status,
  };
  return (await db.add(STORE_PENDING, record)) as number;
}

export async function getPendingAnswers(): Promise<PendingAnswer[]> {
  const db = await getDb();
  return (await db.getAll(STORE_PENDING)).sort(
    (a, b) => (a.created_at ?? 0) - (b.created_at ?? 0),
  );
}

export async function clearPendingAnswers(): Promise<void> {
  const db = await getDb();
  await db.clear(STORE_PENDING);
}

export async function removePendingAnswer(id: number): Promise<void> {
  const db = await getDb();
  await db.delete(STORE_PENDING, id);
}

export async function markPendingStatus(
  id: number,
  status: PendingStatus,
): Promise<void> {
  const db = await getDb();
  const record = await db.get(STORE_PENDING, id);
  if (record) {
    await db.put(STORE_PENDING, { ...record, status });
  }
}

export async function saveSessionSnapshot(snapshot: SessionSnapshot): Promise<void> {
  const db = await getDb();
  await db.put(STORE_SNAPSHOTS, snapshot);
}

export async function getSessionSnapshot(
  sessionId: string,
): Promise<SessionSnapshot | undefined> {
  const db = await getDb();
  return db.get(STORE_SNAPSHOTS, sessionId);
}

export async function deleteSessionSnapshot(sessionId: string): Promise<void> {
  const db = await getDb();
  await db.delete(STORE_SNAPSHOTS, sessionId);
}

/**
 * Отправляет накопившиеся оффлайн-ответы по очереди.
 * Успешные удаляются из очереди, неудачные помечаются как failed.
 */
export async function syncPendingAnswers(): Promise<{
  synced: number;
  failed: number;
}> {
  const items = await getPendingAnswers();
  let synced = 0;
  let failed = 0;

  for (const item of items) {
    if (!item.id) continue;
    await markPendingStatus(item.id, "syncing");
    try {
      await submitAnswer(item.payload);
      await removePendingAnswer(item.id);
      synced += 1;
    } catch {
      await markPendingStatus(item.id, "failed");
      failed += 1;
    }
  }

  return { synced, failed };
}

export interface OfflineSyncState {
  isOnline: boolean;
  pendingCount: number;
  lastSyncAt: number | null;
  syncNow: () => Promise<{ synced: number; failed: number }>;
}

/**
 * Регистрирует слушатели онлайн/оффлайн: при появлении сети
 * автоматически отправляет накопленные ответы.
 */
export function useOfflineSync(): OfflineSyncState {
  const [isOnline, setIsOnline] = useState<boolean>(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [pendingCount, setPendingCount] = useState(0);
  const [lastSyncAt, setLastSyncAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    const refreshCount = async () => {
      if (typeof window === "undefined") return;
      try {
        const items = await getPendingAnswers();
        if (!cancelled) setPendingCount(items.length);
      } catch {
        // IndexedDB недоступен — молча пропускаем
      }
    };

    const handleOnline = async () => {
      if (cancelled) return;
      setIsOnline(true);
      try {
        const result = await syncPendingAnswers();
        if (!cancelled) {
          setLastSyncAt(Date.now());
          await refreshCount();
          void result;
        }
      } catch {
        // ignore
      }
    };

    const handleOffline = () => {
      if (!cancelled) setIsOnline(false);
    };

    refreshCount();
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      cancelled = true;
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const syncNow = async () => {
    const result = await syncPendingAnswers();
    setLastSyncAt(Date.now());
    const items = await getPendingAnswers();
    setPendingCount(items.length);
    return result;
  };

  return { isOnline, pendingCount, lastSyncAt, syncNow };
}
