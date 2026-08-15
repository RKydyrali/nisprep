"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  ArrowRight,
  BrainCircuit,
  BookOpenCheck,
  MessageCircleHeart,
  Timer,
  Zap,
  Target,
  Flame,
} from "lucide-react";

export default function LandingPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations();
  const locale = params.locale;

  const features = [
    {
      icon: <BrainCircuit size={26} />,
      title: t("landing.featureCatTitle"),
      desc: t("landing.featureCatDesc"),
      color: "bg-primary-soft text-primary",
    },
    {
      icon: <BookOpenCheck size={26} />,
      title: t("landing.featureLogTitle"),
      desc: t("landing.featureLogDesc"),
      color: "bg-accent-soft text-accent",
    },
    {
      icon: <MessageCircleHeart size={26} />,
      title: t("landing.featureTgTitle"),
      desc: t("landing.featureTgDesc"),
      color: "bg-blue-50 text-blue-600",
    },
  ];

  const stats = [
    { icon: <Target size={18} />, value: "4", label: t("landing.statChildren") },
    { icon: <Timer size={18} />, value: "30", label: t("landing.statDaily") },
    { icon: <Flame size={18} />, value: "5", label: t("landing.statModes") },
  ];

  return (
    <div>
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-700 via-emerald-800 to-emerald-900 px-6 py-14 text-white shadow-lg sm:px-10 sm:py-20">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-accent/20 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-24 -left-10 h-72 w-72 rounded-full bg-emerald-400/20 blur-3xl"
          aria-hidden
        />

        <div className="relative mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-sm font-medium text-emerald-50 ring-1 ring-white/20">
            <Zap size={14} className="text-amber-300" />
            {t("landing.badge")}
          </span>
          <h1 className="mt-6 text-3xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            {t("landing.title")}{" "}
            <span className="text-amber-300">{t("landing.titleAccent")}</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-emerald-50/90 sm:text-lg">
            {t("landing.subtitle")}
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href={`/${locale}/register`}
              className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-400 px-7 py-3.5 text-base font-bold text-emerald-950 shadow-lg transition-all hover:bg-amber-300 hover:shadow-xl sm:w-auto"
            >
              {t("landing.ctaStart")}
              <ArrowRight size={18} />
            </Link>
            <Link
              href={`/${locale}/login`}
              className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-white/10 px-7 py-3.5 text-base font-semibold text-white ring-1 ring-white/25 transition-colors hover:bg-white/20 sm:w-auto"
            >
              {t("landing.ctaLogin")}
            </Link>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-emerald-50/80">
            {stats.map((stat) => (
              <span key={stat.label} className="flex items-center gap-2">
                <span className="text-amber-300">{stat.icon}</span>
                <span className="font-bold text-white">{stat.value}</span> {stat.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-10 grid gap-5 md:grid-cols-3">
        {features.map((feature) => (
          <div
            key={feature.title}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
          >
            <span
              className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl ${feature.color}`}
            >
              {feature.icon}
            </span>
            <h3 className="mt-4 text-lg font-bold text-ink">{feature.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.desc}</p>
          </div>
        ))}
      </section>

      <section className="mt-10 rounded-3xl border border-emerald-100 bg-emerald-50/60 p-8 text-center sm:p-12">
        <h2 className="text-2xl font-extrabold text-ink sm:text-3xl">
          {t("landing.title")}
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-slate-600">{t("landing.subtitle")}</p>
        <Link
          href={`/${locale}/register`}
          className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-primary px-7 py-3.5 font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
        >
          {t("landing.ctaStart")}
          <ArrowRight size={18} />
        </Link>
      </section>
    </div>
  );
}
