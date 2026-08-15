"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  BookOpenCheck,
  CheckCircle2,
  Flame,
  Loader2,
  RefreshCw,
  Repeat,
  Send,
  XCircle,
} from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import MathRenderer from "@/components/MathRenderer";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import {
  getDueItems,
  submitRevision,
  choiceLabel,
  isNetworkError,
  type AnswerValue,
  type DueItem,
} from "@/lib/api";
import { currentLocale } from "@/lib/auth";

function formatAnswer(value: AnswerValue | unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
  }
  return String(value ?? "");
}

function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(locale === "kk" ? "kk-KZ" : "ru-RU", {
    day: "numeric",
    month: "short",
  });
}

export default function ErrorLogPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("errorLog");
  const router = useRouter();
  const { toast } = useToast();
  const locale = currentLocale();

  const [items, setItems] = useState<DueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [active, setActive] = useState<DueItem | null>(null);
  const [selectedChoice, setSelectedChoice] = useState<number | null>(null);
  const [numericInput, setNumericInput] = useState("");
  const [textInput, setTextInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sessionError, setSessionError] = useState(false);
  const [feedback, setFeedback] = useState<{
    isCorrect: boolean;
    correctAnswer: unknown;
    yourAnswer: AnswerValue | null;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const data = await getDueItems();
      setItems(data.items);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openItem = (item: DueItem) => {
    setActive(item);
    setSelectedChoice(null);
    setNumericInput("");
    setTextInput("");
    setFeedback(null);
    setSessionError(false);
  };

  const closeItem = () => {
    setActive(null);
    setFeedback(null);
  };

  const handleSubmit = async () => {
    if (!active || submitting) return;

    const q = active.question;
    let answer: AnswerValue | null = null;
    if (q.answer_type === "choice") {
      answer = selectedChoice;
    } else if (q.answer_type === "text") {
      if (!textInput.trim()) return;
      answer = textInput.trim();
    } else {
      if (!numericInput.trim()) return;
      answer = Number(numericInput.replace(",", "."));
    }
    if (answer === null) return;

    setSubmitting(true);
    try {
      const result = await submitRevision({
        template_id: q.template_id,
        params: q.params,
        answer,
        time_taken_sec: 60,
      });
      setFeedback({
        isCorrect: result.is_correct,
        correctAnswer: result.correct_answer,
        yourAnswer: answer,
      });
      if (result.is_correct) {
        setItems((prev) => prev.filter((item) => item.item_id !== active.item_id));
        toast(t("correct"), "success");
      } else {
        toast(t("incorrect"), "info");
      }
    } catch (err) {
      if (isNetworkError(err)) {
        toast(t("submitError"), "error");
      } else {
        // Backend может не принять ревизию без активной сессии — показываем понятное сообщение
        setSessionError(true);
        setFeedback(null);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "w-full rounded-2xl border-2 border-slate-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-primary";

  return (
    <AuthGuard role="child">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
            {t("title")}
          </h1>
          <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
        </div>
        {items.length > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary-soft px-3.5 py-1.5 text-sm font-bold text-primary">
            <BookOpenCheck size={15} />
            {t("dueToday")}: {items.length}
          </span>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted">
          <Loader2 size={22} className="animate-spin text-primary" />
          {t("loading")}
        </div>
      ) : loadError ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-slate-200 bg-white py-14 text-center">
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
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-4 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <CheckCircle2 size={30} />
          </span>
          <p className="max-w-sm text-sm text-muted">{t("none")}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const skillName =
              item.question.micro_skill &&
              (locale === "kk"
                ? item.question.micro_skill.name_kk
                : item.question.micro_skill.name_ru);
            return (
              <div
                key={item.item_id}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <span className="rounded-full bg-danger-soft px-2.5 py-1 text-xs font-bold text-danger">
                    {t("reviewNum", { n: item.review_number })}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-muted">
                    {t("interval", { days: item.interval_days })}
                  </span>
                  <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent">
                    {t("strength")}: {Math.round(item.ef * 100)}%
                  </span>
                  <span className="text-xs text-muted">
                    {t("wrongCount")}: {item.wrong_count} · {t("nextReview")}:{" "}
                    {formatDate(item.next_review_at, locale)}
                  </span>
                </div>

                {skillName && (
                  <p className="mt-3 text-[11px] font-bold uppercase tracking-wide text-muted">
                    {skillName}
                  </p>
                )}
                <MathRenderer
                  text={item.question.question_text}
                  className="mt-1.5 text-sm leading-relaxed text-ink"
                />

                <button
                  type="button"
                  onClick={() => openItem(item)}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-primary-hover"
                >
                  <Repeat size={15} />
                  {t("repeat")}
                </button>
              </div>
            );
          })}
        </div>
      )}

      <Modal
        open={active !== null}
        onClose={closeItem}
        title={t("modalTitle")}
        wide
      >
        {active && (
          <div className="space-y-5">
            {active.question.micro_skill && (
              <p className="text-[11px] font-bold uppercase tracking-wide text-muted">
                {locale === "kk"
                  ? active.question.micro_skill.name_kk
                  : active.question.micro_skill.name_ru}
              </p>
            )}
            <MathRenderer
              text={active.question.question_text}
              className="text-sm leading-relaxed text-ink"
            />

            {active.question.answer_type === "choice" && active.question.choices && (
              <div className="grid gap-2.5 sm:grid-cols-2">
                {active.question.choices.map((choice, idx) => {
                  const selected = selectedChoice === idx;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedChoice(idx)}
                      disabled={!!feedback}
                      className={`flex items-start gap-2.5 rounded-2xl border-2 px-3.5 py-3 text-left text-sm transition-all ${
                        selected
                          ? "border-primary bg-primary-soft text-primary"
                          : "border-slate-200 bg-white text-slate-700 hover:border-primary/40"
                      } disabled:opacity-60`}
                    >
                      <span
                        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs font-extrabold ${
                          selected ? "bg-primary text-white" : "bg-slate-100 text-muted"
                        }`}
                      >
                        {choiceLabel(idx)}
                      </span>
                      <MathRenderer text={choice} className="min-w-0 flex-1" />
                    </button>
                  );
                })}
              </div>
            )}

            {(active.question.answer_type === "integer" ||
              active.question.answer_type === "float") && (
              <input
                type="number"
                step={active.question.answer_type === "float" ? "0.01" : "1"}
                inputMode={active.question.answer_type === "float" ? "decimal" : "numeric"}
                value={numericInput}
                onChange={(e) => setNumericInput(e.target.value)}
                disabled={!!feedback}
                placeholder={t("answerPhNumeric")}
                className={inputClass}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleSubmit();
                }}
              />
            )}

            {active.question.answer_type === "text" && (
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                disabled={!!feedback}
                placeholder={t("answerPhText")}
                rows={3}
                className={`${inputClass} resize-none`}
              />
            )}

            {sessionError && (
              <div className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-4">
                <p className="text-sm font-bold text-danger">{t("sessionExpired")}</p>
                <button
                  type="button"
                  onClick={() => {
                    closeItem();
                    router.push(`/${locale}/trainer`);
                  }}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-danger px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-red-700"
                >
                  <Flame size={15} />
                  {t("startNew")}
                </button>
              </div>
            )}

            {feedback && (
              <div
                className={`rounded-2xl border px-4 py-4 ${
                  feedback.isCorrect
                    ? "border-primary/25 bg-primary-soft/60"
                    : "border-danger/25 bg-danger-soft/60"
                }`}
              >
                <p
                  className={`flex items-center gap-1.5 text-base font-extrabold ${
                    feedback.isCorrect ? "text-primary" : "text-danger"
                  }`}
                >
                  {feedback.isCorrect ? <CheckCircle2 size={19} /> : <XCircle size={19} />}
                  {feedback.isCorrect ? t("correct") : t("incorrect")}
                </p>
                {!feedback.isCorrect && (
                  <p className="mt-1 text-sm text-slate-700">
                    {t("correctAnswer")}:{" "}
                    <b className="font-mono">{formatAnswer(feedback.correctAnswer)}</b>
                  </p>
                )}
                <p className="mt-1 text-xs text-muted">
                  {t("yourAnswer")}: <b className="font-mono">{formatAnswer(feedback.yourAnswer)}</b>
                </p>
              </div>
            )}

            {!feedback && !sessionError && (
              <button
                type="button"
                onClick={() => void handleSubmit()}
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={15} />}
                {t("submit")}
              </button>
            )}

            {feedback && (
              <button
                type="button"
                onClick={closeItem}
                className="w-full rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
              >
                {t("close")}
              </button>
            )}
          </div>
        )}
      </Modal>
    </AuthGuard>
  );
}
