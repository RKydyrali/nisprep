"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Sparkles } from "lucide-react";

interface TextChunkerProps {
  text: string;
  lang: "ru" | "kk";
}

const KEY_MARKERS_RU = ["главный", "потому что", "следовательно", "важно"];
const KEY_MARKERS_KK = ["басты", "себебі", "сондықтан", "маңызды"];

const COLLAPSE_THRESHOLD = 500;

function splitSentences(paragraph: string): string[] {
  return paragraph
    .split(/(?<=[.!?…])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function isKeySentence(sentence: string, lang: "ru" | "kk"): boolean {
  const markers = lang === "kk" ? KEY_MARKERS_KK : KEY_MARKERS_RU;
  const lower = sentence.toLowerCase();
  return markers.some((marker) => lower.includes(marker));
}

/**
 * Разбивка длинного текста на смысловые блоки: ключевые предложения
 * (маркеры причины/следствия/важности) подсвечиваются янтарным маркером.
 */
export default function TextChunker({ text, lang }: TextChunkerProps) {
  const t = useTranslations();
  const [expanded, setExpanded] = useState(false);

  const paragraphs = useMemo(() => {
    return text
      .split(/\n{2,}|\n/)
      .map((block) => block.trim())
      .filter(Boolean)
      .map((block) => splitSentences(block).flatMap((s) => [s]));
  }, [text]);

  const needsCollapse = text.length > COLLAPSE_THRESHOLD;
  const visible = needsCollapse && !expanded ? paragraphs.slice(0, 2) : paragraphs;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
      <div className="space-y-3">
        {visible.map((sentences, pi) => (
          <div key={pi} className="space-y-1.5">
            {sentences.map((sentence, si) => {
              const key = isKeySentence(sentence, lang);
              return (
                <p
                  key={si}
                  className={
                    key
                      ? "rounded bg-accent-soft px-1.5 py-0.5 text-[15px] leading-relaxed text-ink"
                      : "text-[15px] leading-relaxed text-slate-700"
                  }
                >
                  {sentence}
                </p>
              );
            })}
          </div>
        ))}
      </div>

      {needsCollapse && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-accent bg-accent-soft px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-amber-200"
        >
          <Sparkles size={14} className="text-accent" />
          {expanded ? t("textChunker.hide") : t("textChunker.show")}
        </button>
      )}
    </div>
  );
}
