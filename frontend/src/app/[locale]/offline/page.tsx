"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { CheckCircle2, CloudOff, Loader2, RefreshCw } from "lucide-react";
import {
  getPendingAnswers,
  syncPendingAnswers,
  useOfflineSync,
  type PendingAnswer,
} from "@/lib/offline-sync";
import { currentLocale } from "@/lib/auth";

export default function OfflinePage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("offline");
  const locale = params.locale;

  const { isOnline, pendingCount, syncNow } = useOfflineSync();
  const [pending, setPending] = useState<PendingAnswer[]>([]);
  const [syncing, setSyncing] = useState(false);

  const refresh = async () => {
    try {
      setPending(await getPendingAnswers());
    } catch {
      setPending([]);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    void refresh();
  }, [pendingCount]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await syncNow();
      await refresh();
    } finally {
      setSyncing(false);
    }
  };

  const cl = currentLocale();

  return (
    <div className="mx-auto max-w-lg">
      <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <span
          className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${
            isOnline ? "bg-primary-soft text-primary" : "bg-accent-soft text-accent"
          }`}
        >
          {isOnline ? <CheckCircle2 size={32} /> : <CloudOff size={32} />}
        </span>
        <h1 className="mt-5 text-2xl font-extrabold text-ink">{t("title")}</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">{t("subtitle")}</p>

        {isOnline && (
          <Link
            href={`/${cl}/trainer`}
            className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-primary px-6 py-3 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
          >
            {t("onlineBtn")}
          </Link>
        )}

        <div className="mt-7 border-t border-slate-100 pt-5 text-left">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-ink">{t("pending")}</h2>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-muted">
              {pending.length}
            </span>
          </div>

          {pending.length === 0 ? (
            <p className="mt-3 text-sm text-muted">{t("none")}</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {pending.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3.5 py-2.5 text-sm"
                >
                  <span className="truncate font-mono text-xs text-muted">
                    {item.session_id.slice(0, 16)}…
                  </span>
                  <span className="flex items-center gap-1.5">
                    {item.status === "failed" && (
                      <span className="text-xs font-semibold text-danger">error</span>
                    )}
                    {item.status === "syncing" && (
                      <Loader2 size={13} className="animate-spin text-primary" />
                    )}
                    <span className="text-xs font-semibold text-muted">
                      {new Date(item.created_at).toLocaleTimeString(cl === "kk" ? "kk-KZ" : "ru-RU", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}

          {pending.length > 0 && (
            <button
              type="button"
              onClick={() => void handleSync()}
              disabled={syncing || !isOnline}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {syncing ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <RefreshCw size={15} />
              )}
              {syncing ? t("syncing") : t("syncNow")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
