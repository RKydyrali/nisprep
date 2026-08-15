"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, RefreshCw } from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import ReadinessGauge from "@/components/ReadinessGauge";
import { HistoryChart, SkillGraph, ThetaBars, WeakSkills } from "@/components/charts";
import { getReadiness, type Readiness } from "@/lib/api";

export default function ChildAnalyticsPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("analytics");
  const { locale } = params;

  const [data, setData] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setData(await getReadiness());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AuthGuard role="child">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
          {t("title")}
        </h1>
        <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-20 text-muted">
          <Loader2 size={24} className="animate-spin text-primary" />
          {t("loading")}
        </div>
      ) : error || !data ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-slate-200 bg-white py-16 text-center">
          <p className="text-sm font-medium text-ink">{t("loadError")}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-primary shadow-sm hover:bg-primary-soft"
          >
            <RefreshCw size={14} />
            {t("retry")}
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-center text-sm font-bold text-ink">{t("grantGauge")}</p>
              <div className="mt-3">
                <ReadinessGauge
                  value={Math.round(data.p_grant * 100)}
                  band={data.band}
                  bandLabel={
                    data.band === "high"
                      ? t("bandHigh")
                      : data.band === "medium"
                        ? t("bandMedium")
                        : t("bandLow")
                  }
                  caption={t("grantGauge")}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2 lg:content-start">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t("psi")}
                </p>
                <p className="mt-1 text-xl font-extrabold tabular-nums text-ink">
                  {data.psi.toFixed(2)}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t("pGrant")}
                </p>
                <p className="mt-1 text-xl font-extrabold tabular-nums text-ink">
                  {Math.round(data.p_grant * 100)}%
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t("tSpeed")}
                </p>
                <p className="mt-1 text-xl font-extrabold tabular-nums text-ink">
                  {data.t_speed.toFixed(1)} с
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="mb-4 text-base font-bold text-ink">{t("thetaTitle")}</h2>
            <ThetaBars
              theta={data.theta}
              labels={{
                math: t("math"),
                quant: t("quant"),
                natSci: t("natSci"),
                lang: t("lang"),
              }}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="mb-4 text-base font-bold text-ink">{t("weakTitle")}</h2>
              {data.weak_skills.length === 0 ? (
                <p className="text-sm text-muted">{t("noWeak")}</p>
              ) : (
                <WeakSkills skills={data.weak_skills} locale={locale} />
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="text-base font-bold text-ink">{t("graphTitle")}</h2>
              <p className="mb-2 mt-0.5 text-xs text-muted">{t("graphHint")}</p>
              <SkillGraph nodes={data.graph.nodes} edges={data.graph.edges} />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="mb-4 text-base font-bold text-ink">{t("historyTitle")}</h2>
            {data.history.dates.length > 0 ? (
              <HistoryChart history={data.history} />
            ) : (
              <p className="text-sm text-muted">{t("noData")}</p>
            )}
          </div>
        </div>
      )}
    </AuthGuard>
  );
}
