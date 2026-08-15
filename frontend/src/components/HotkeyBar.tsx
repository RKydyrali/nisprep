"use client";

import { useTranslations } from "next-intl";
import { Keyboard } from "lucide-react";

/**
 * Подсказка горячих клавиш тренажёра: выбор варианта, подтверждение, переход.
 */
export default function HotkeyBar() {
  const t = useTranslations("trainer");

  const hints = [
    { keys: ["1", "2", "3", "4"], label: t("hintChoice") },
    { keys: ["Enter"], label: t("hintEnter") },
    { keys: ["Space"], label: t("hintNext") },
  ];

  return (
    <div className="flex flex-wrap items-center justify-center gap-3 rounded-2xl border border-accent/60 bg-accent-soft/60 px-4 py-2.5">
      <span className="flex items-center gap-1.5 text-xs font-medium text-slate-600">
        <Keyboard size={14} className="text-accent" />
        {t("hintKeys")}
      </span>
      {hints.map((hint) => (
        <span key={hint.label} className="flex items-center gap-1.5">
          {hint.keys.map((key) => (
            <kbd
              key={key}
              className="rounded-md border border-amber-400/60 bg-white px-1.5 py-0.5 font-mono text-[11px] font-semibold text-ink shadow-sm"
            >
              {key}
            </kbd>
          ))}
          <span className="text-xs text-slate-600">{hint.label}</span>
        </span>
      ))}
    </div>
  );
}
