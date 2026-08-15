"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  BarChart3,
  CheckCircle2,
  Clock3,
  Flame,
  Link2Off,
  Pencil,
  Trash2,
} from "lucide-react";
import type { ChildUser, Readiness } from "@/lib/api";

interface ChildCardProps {
  child: ChildUser;
  locale: string;
  readiness: Readiness | null;
  onEdit: (child: ChildUser) => void;
  onDelete: (child: ChildUser) => void;
}

function StatusBadge({ child }: { child: ChildUser }) {
  const t = useTranslations("dashboard");

  if (child.is_verified) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-primary ring-1 ring-primary/20">
        <CheckCircle2 size={13} />
        {t("verified")}
      </span>
    );
  }
  if (child.telegram_chat_id) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-accent ring-1 ring-accent/30">
        <Clock3 size={13} />
        {t("awaiting")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-muted ring-1 ring-slate-200">
      <Link2Off size={13} />
      {t("unlinked")}
    </span>
  );
}

function ThetaSparkline({ history }: { history: Readiness["history"] }) {
  const series = history?.series;
  if (!series || series.math.length === 0) return null;

  const W = 200;
  const H = 40;
  const values = [...series.math, ...series.quant, ...series.nat_sci, ...series.lang];
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const range = max - min || 1;
  const n = Math.max(2, series.math.length);

  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => H - ((v - min) / range) * H;

  const line = (key: keyof Readiness["history"]["series"]) =>
    series[key]
      .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
      .join(" ");

  const colors = ["#047857", "#F59E0B", "#2563EB", "#7C3AED"];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-10 w-full" preserveAspectRatio="none">
      {(Object.keys(series) as (keyof typeof series)[]).map((key, idx) => (
        <path
          key={key}
          d={line(key)}
          fill="none"
          stroke={colors[idx]}
          strokeWidth={2}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}

export default function ChildCard({
  child,
  locale,
  readiness,
  onEdit,
  onDelete,
}: ChildCardProps) {
  const t = useTranslations("dashboard");
  const langName = child.language === "kk" ? t("langKk") : t("langRu");

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-bold text-ink">{child.full_name}</h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-muted">
              {t("langBadge", { lang: langName })}
            </span>
          </div>
          <div className="mt-1.5">
            <StatusBadge child={child} />
          </div>
        </div>
        <span className="shrink-0 rounded-2xl bg-primary-soft px-3 py-1.5 text-center">
          <span className="block text-sm font-extrabold tabular-nums text-primary">
            {Math.round(child.current_elo)}
          </span>
          <span className="block text-[10px] font-semibold uppercase tracking-wide text-primary/70">
            {t("elo")}
          </span>
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-slate-50 px-2 py-2.5">
          <div className="flex items-center justify-center gap-1 text-sm font-bold text-ink">
            <Flame size={14} className="text-accent" />
            {child.streak_days}
          </div>
          <div className="text-[10px] font-medium text-muted">{t("streak")}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-2 py-2.5">
          <div className="text-sm font-bold tabular-nums text-ink">{child.total_solved}</div>
          <div className="text-[10px] font-medium text-muted">{t("solved")}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-2 py-2.5">
          <div className="text-sm font-bold tabular-nums text-ink">
            {child.total_solved > 0
              ? Math.round((child.total_correct / child.total_solved) * 100)
              : 0}
            %
          </div>
          <div className="text-[10px] font-medium text-muted">{t("accuracy")}</div>
        </div>
      </div>

      {readiness && (
        <div className="mt-4">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {t("thetaTrend")}
          </p>
          <ThetaSparkline history={readiness.history} />
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        <Link
          href={`/${locale}/dashboard/${child.id}`}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-primary px-3 py-2.5 text-sm font-bold text-white transition-colors hover:bg-primary-hover"
        >
          <BarChart3 size={15} />
          {t("analytics")}
        </Link>
        <button
          type="button"
          onClick={() => onEdit(child)}
          aria-label={t("edit")}
          className="rounded-xl border border-slate-200 bg-white p-2.5 text-muted shadow-sm transition-colors hover:border-primary/40 hover:text-primary"
        >
          <Pencil size={15} />
        </button>
        <button
          type="button"
          onClick={() => onDelete(child)}
          aria-label={t("delete")}
          className="rounded-xl border border-slate-200 bg-white p-2.5 text-muted shadow-sm transition-colors hover:border-danger/40 hover:text-danger"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}
