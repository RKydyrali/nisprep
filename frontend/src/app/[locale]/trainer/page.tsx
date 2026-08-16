"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  Flame,
  Infinity as InfinityIcon,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Timer,
  XCircle,
  BookOpenText,
  Calculator,
  Zap,
} from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import HotkeyBar from "@/components/HotkeyBar";
import MathRenderer from "@/components/MathRenderer";
import MicroTimer from "@/components/MicroTimer";
import TextChunker from "@/components/TextChunker";
import { useToast } from "@/components/Toast";
import {
  startSession,
  submitAnswer,
  choiceLabel,
  isNetworkError,
  type AnswerValue,
  type Question,
  type SessionMode,
  type SubmitResult,
} from "@/lib/api";
import { currentLocale } from "@/lib/auth";
import {
  listSessionSnapshots,
  saveOfflineAnswer,
  saveSessionSnapshot,
  useOfflineSync,
} from "@/lib/offline-sync";

type Screen = "modes" | "question" | "results";

const MODES: {
  id: SessionMode;
  icon: typeof Zap;
  color: string;
  time: string;
}[] = [
  { id: "sprint", icon: Zap, color: "text-accent bg-accent-soft", time: "30с" },
  { id: "cat", icon: BrainCircuit, color: "text-primary bg-primary-soft", time: "CAT" },
  { id: "day1", icon: Calculator, color: "text-blue-600 bg-blue-50", time: "90с" },
  { id: "day2", icon: BookOpenText, color: "text-violet-600 bg-violet-50", time: "120с" },
  { id: "free", icon: InfinityIcon, color: "text-slate-600 bg-slate-100", time: "∞" },
];

function formatAnswer(value: AnswerValue | unknown): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)));
  }
  return String(value ?? "");
}

export default function TrainerPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("trainer");
  const tc = useTranslations("common");
  const router = useRouter();
  const { toast } = useToast();
  const { isOnline, syncNow } = useOfflineSync();
  const locale = currentLocale();

  const [screen, setScreen] = useState<Screen>("modes");
  const [mode, setMode] = useState<SessionMode | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [selectedChoice, setSelectedChoice] = useState<number | null>(null);
  const [numericInput, setNumericInput] = useState("");
  const [textInput, setTextInput] = useState("");
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [offline, setOffline] = useState(false);

  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [finalElo, setFinalElo] = useState<number | null>(null);
  const [finalStreak, setFinalStreak] = useState(0);

  const advanceTimerRef = useRef<number | null>(null);
  const submittingRef = useRef(false);

  // Восстановление прерванной сессии после перезагрузки страницы.
  useEffect(() => {
    void (async () => {
      try {
        const snapshots = await listSessionSnapshots();
        const latest = snapshots[snapshots.length - 1];
        if (latest?.question) {
          setMode((latest.mode as SessionMode) ?? "free");
          setQuestion(latest.question);
          setResult(null);
          setScreen("question");
        }
      } catch {
        // снапшоты недоступны — просто стартуем заново
      }
    })();
  }, []);

  const clearAdvanceTimer = useCallback(() => {
    if (advanceTimerRef.current !== null) {
      window.clearTimeout(advanceTimerRef.current);
      advanceTimerRef.current = null;
    }
  }, []);

  const handleStart = async (selectedMode: SessionMode) => {
    if (starting) return;
    setStarting(true);
    try {
      const q = await startSession(selectedMode);
      setMode(selectedMode);
      setQuestion(q);
      setResult(null);
      setSelectedChoice(null);
      setNumericInput("");
      setTextInput("");
      setCorrectCount(0);
      setAnsweredCount(0);
      setOffline(false);
      setScreen("question");
    } catch (err) {
      if (isNetworkError(err)) {
        toast(t("submitError"), "error");
      } else {
        toast(t("startError"), "error");
      }
    } finally {
      setStarting(false);
    }
  };

  const doSubmit = useCallback(
    async (answer: AnswerValue, timedOut: boolean) => {
      if (!question || submittingRef.current) return;
      submittingRef.current = true;
      setSubmitting(true);

      const timeLimit = question.time_limit_sec;
      const elapsed = timedOut ? timeLimit : Math.max(0.5, timeLimit * 0.9);

      const payload = {
        session_id: question.session_id,
        template_id: question.template_id,
        params: question.params,
        answer,
        time_taken_sec: elapsed,
      };

      try {
        const res = await submitAnswer(payload);
        setResult(res);
        setAnsweredCount((n) => n + 1);
        if (res.is_correct) setCorrectCount((n) => n + 1);
        if (res.elo_after !== null && res.elo_after !== undefined) {
          setFinalElo(res.elo_after);
        }
        setFinalStreak(res.streak_days);
        setSubmitting(false);
        submittingRef.current = false;

        if (res.next_question) {
          advanceTimerRef.current = window.setTimeout(() => {
            advanceTimerRef.current = null;
            setQuestion(res.next_question);
            setResult(null);
            setSelectedChoice(null);
            setNumericInput("");
            setTextInput("");
            setOffline(false);
          }, 1200);
        } else if (res.session_finished) {
          advanceTimerRef.current = window.setTimeout(() => {
            advanceTimerRef.current = null;
            setScreen("results");
          }, 1200);
        }
      } catch (err) {
        setSubmitting(false);
        submittingRef.current = false;
        if (isNetworkError(err)) {
          setOffline(true);
          await saveOfflineAnswer(payload);
          await saveSessionSnapshot({
            session_id: question.session_id,
            saved_at: Date.now(),
            question,
            mode: question.mode,
          });
          toast(t("offlineSaved"), "info");
        } else {
          toast(t("submitError"), "error");
        }
      }
    },
    [question, toast, t, syncNow],
  );

  const handleTimeout = useCallback(() => {
    // F-H1: таймер не должен сабмитить после того, как ответ уже получен.
    if (!question || submittingRef.current || result) return;
    const timedOutAnswer: AnswerValue =
      question.answer_type === "choice" ? -1 : question.answer_type === "text" ? "999999" : 999999.42;
    void doSubmit(timedOutAnswer, true);
  }, [question, doSubmit, result]);

  const canSubmit =
    (question?.answer_type === "choice" && selectedChoice !== null) ||
    (question?.answer_type === "integer" && numericInput.trim() !== "") ||
    (question?.answer_type === "float" && numericInput.trim() !== "") ||
    (question?.answer_type === "text" && textInput.trim() !== "");

  const handleManualSubmit = useCallback(() => {
    if (!question || !canSubmit || submittingRef.current) {
      if (!canSubmit && !submittingRef.current) toast(t("noAnswer"), "info");
      return;
    }
    const answer: AnswerValue =
      question.answer_type === "choice"
        ? (selectedChoice as number)
        : question.answer_type === "text"
          ? textInput.trim()
          : Number(numericInput.replace(",", "."));
    void doSubmit(answer, false);
  }, [question, canSubmit, selectedChoice, textInput, numericInput, doSubmit, toast, t]);

  const handleAdvanceNow = useCallback(() => {
    if (!result) return;
    clearAdvanceTimer();
    if (result.next_question) {
      setQuestion(result.next_question);
      setResult(null);
      setSelectedChoice(null);
      setNumericInput("");
      setTextInput("");
      setOffline(false);
    } else if (result.session_finished) {
      setScreen("results");
    }
  }, [result, clearAdvanceTimer]);

  const handleExit = useCallback(() => {
    if (screen === "question" && question) {
      const confirmed = window.confirm(t("exitConfirm"));
      if (confirmed) {
        router.push(`/${locale}/analytics`);
      }
    }
  }, [screen, question, router, locale, t]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (screen !== "question" || !question) return;

      if (e.key === "Escape") {
        handleExit();
        return;
      }

      if (result) {
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          handleAdvanceNow();
        }
        return;
      }

      if (submitting) return;

      if (question.answer_type === "choice") {
        const idx = parseInt(e.key, 10) - 1;
        if (idx >= 0 && idx < (question.choices?.length ?? 0)) {
          e.preventDefault();
          setSelectedChoice(idx);
        }
      }

      if (e.key === "Enter") {
        e.preventDefault();
        handleManualSubmit();
      }
    },
    [screen, question, result, submitting, handleExit, handleAdvanceNow, handleManualSubmit],
  );

  useEffect(() => {
    if (screen !== "question") return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("beforeunload", handleBeforeUnload);
      clearAdvanceTimer();
    };
  }, [screen, handleKeyDown, clearAdvanceTimer]);

  useEffect(() => {
    return () => clearAdvanceTimer();
  }, [clearAdvanceTimer]);

  const modeMeta = MODES.find((m) => m.id === mode);
  const skillName =
    question?.micro_skill &&
    (locale === "kk" ? question.micro_skill.name_kk : question.micro_skill.name_ru);
  const totalQuestions = question?.total_questions ?? 1;
  const progressPct = Math.min(100, Math.round((answeredCount / totalQuestions) * 100));
  const timerKey = question ? `${question.session_id}:${question.question_id}` : "none";

  if (screen === "modes") {
    return (
      <AuthGuard role="child">
        <div className="mx-auto max-w-3xl">
          <div className="text-center">
            <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
              {t("title")}
            </h1>
            <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
          </div>

          <p className="mt-8 mb-3 text-sm font-bold uppercase tracking-wide text-muted">
            {t("pickMode")}
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {MODES.map((m) => {
              const Icon = m.icon;
              return (
                <button
                  key={m.id}
                  type="button"
                  disabled={starting}
                  onClick={() => void handleStart(m.id)}
                  className="group flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md disabled:opacity-60"
                >
                  <span
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${m.color}`}
                  >
                    <Icon size={24} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-base font-bold text-ink">
                        {t(`${m.id}Name`)}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-muted">
                        {m.time}
                      </span>
                    </span>
                    <span className="mt-1 block text-sm leading-relaxed text-slate-600">
                      {t(`${m.id}Desc`)}
                    </span>
                  </span>
                  <span className="mt-3 shrink-0 text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    <Play size={18} fill="currentColor" />
                  </span>
                </button>
              );
            })}
          </div>

          {starting && (
            <div className="mt-6 flex items-center justify-center gap-2 text-sm font-medium text-muted">
              <Loader2 size={18} className="animate-spin text-primary" />
              {t("starting")}
            </div>
          )}
        </div>
      </AuthGuard>
    );
  }

  if (screen === "results" && mode) {
    const accuracy = answeredCount > 0 ? Math.round((correctCount / answeredCount) * 100) : 0;
    return (
      <AuthGuard role="child">
        <div className="mx-auto max-w-lg">
          <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <span
              className={`mx-auto flex h-20 w-20 items-center justify-center rounded-full ${
                accuracy >= 60 ? "bg-primary-soft text-primary" : "bg-accent-soft text-accent"
              }`}
            >
              {accuracy >= 60 ? <CheckCircle2 size={40} /> : <Sparkles size={40} />}
            </span>
            <h2 className="mt-5 text-2xl font-extrabold text-ink">{t("resultsTitle")}</h2>
            <p className="mt-1 text-sm text-muted">{t(`${mode}Name`)}</p>

            <div className="mt-6 grid grid-cols-3 gap-3">
              <div className="rounded-2xl bg-slate-50 px-2 py-4">
                <p className="text-xl font-extrabold tabular-nums text-ink">
                  {correctCount}/{answeredCount}
                </p>
                <p className="mt-0.5 text-[11px] font-semibold text-muted">{t("score")}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 px-2 py-4">
                <p className="text-xl font-extrabold tabular-nums text-ink">{accuracy}%</p>
                <p className="mt-0.5 text-[11px] font-semibold text-muted">{t("accuracy")}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 px-2 py-4">
                <p className="text-xl font-extrabold tabular-nums text-ink">
                  {finalElo !== null ? Math.round(finalElo) : "—"}
                </p>
                <p className="mt-0.5 text-[11px] font-semibold text-muted">{t("finalElo")}</p>
              </div>
            </div>

            {finalStreak > 0 && (
              <p className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-4 py-1.5 text-sm font-bold text-ink">
                <Flame size={15} className="text-accent" />
                {t("streak", { days: finalStreak })}
              </p>
            )}

            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => void handleStart(mode)}
                className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
              >
                <RotateCcw size={16} />
                {t("playAgain")}
              </button>
              <button
                type="button"
                onClick={() => router.push(`/${locale}/analytics`)}
                className="flex flex-1 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-sm font-bold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
              >
                <Activity size={16} />
                {t("toDashboard")}
              </button>
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!question) {
    return null;
  }

  const timeLimited = question.time_limit_sec <= 300 && mode !== "free";
  const isFreeMode = mode === "free";

  return (
    <AuthGuard role="child">
      <div className="mx-auto max-w-3xl">
        {!isOnline && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-accent/50 bg-accent-soft px-4 py-3 text-sm font-semibold text-ink">
            <Timer size={16} className="text-accent" />
            {t("offlineSaved")}
          </div>
        )}
        {offline && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl border border-accent/50 bg-accent-soft px-4 py-3 text-sm font-semibold text-ink">
            <RefreshCw size={16} className="animate-spin text-accent" />
            {t("offlineSaved")}
            <button
              type="button"
              className="ml-auto rounded-full bg-white px-3 py-1 text-xs font-bold text-primary shadow-sm"
              onClick={() => void syncNow()}
            >
              {t("retry")}
            </button>
          </div>
        )}

        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {modeMeta && (
              <span
                className={`flex h-9 w-9 items-center justify-center rounded-xl ${modeMeta.color}`}
              >
                <modeMeta.icon size={18} />
              </span>
            )}
            <span className="text-sm font-bold text-ink">
              {t("questionOf", { current: answeredCount + 1, total: totalQuestions })}
            </span>
          </div>
          <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 sm:px-7">
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-wide text-muted">
                {t("skill")}
              </p>
              <p className="truncate text-sm font-semibold text-ink">{skillName}</p>
            </div>
            {timeLimited ? (
              <MicroTimer key={timerKey} seconds={question.time_limit_sec} onExpire={handleTimeout} />
            ) : (
              <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5 text-sm font-bold text-muted">
                <InfinityIcon size={16} />
                {t("freeName")}
              </span>
            )}
          </div>

          <div className="px-5 py-5 sm:px-7 sm:py-7">
            <MathRenderer
              text={question.question_text}
              className="text-[15px] leading-relaxed text-ink"
            />

            {mode === "day2" && (
              <div className="mt-4">
                <TextChunker text={question.question_text} lang={locale === "kk" ? "kk" : "ru"} />
              </div>
            )}

            <div className="mt-6">
              {question.answer_type === "choice" && question.choices && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {question.choices.map((choice, idx) => {
                    const selected = selectedChoice === idx;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setSelectedChoice(idx)}
                        disabled={!!result}
                        className={`flex items-start gap-3 rounded-2xl border-2 px-4 py-3.5 text-left text-sm transition-all ${
                          selected
                            ? "border-primary bg-primary-soft text-primary"
                            : "border-slate-200 bg-white text-slate-700 hover:border-primary/40 hover:bg-slate-50"
                        } disabled:cursor-not-allowed disabled:opacity-60`}
                      >
                        <span
                          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-extrabold ${
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

              {(question.answer_type === "integer" || question.answer_type === "float") && (
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    step={question.answer_type === "float" ? "0.01" : "1"}
                    inputMode={question.answer_type === "float" ? "decimal" : "numeric"}
                    value={numericInput}
                    onChange={(e) => setNumericInput(e.target.value)}
                    disabled={!!result}
                    placeholder={t("answerPhNumeric")}
                    className="w-full flex-1 rounded-2xl border-2 border-slate-200 bg-white px-4 py-3.5 font-mono text-base text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-primary disabled:opacity-60"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleManualSubmit();
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleManualSubmit}
                    disabled={!canSubmit || submitting || !!result}
                    className="flex h-12 items-center gap-2 rounded-2xl bg-primary px-5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={15} />}
                    {t("submit")}
                  </button>
                </div>
              )}

              {question.answer_type === "text" && (
                <div className="space-y-3">
                  <textarea
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    disabled={!!result}
                    placeholder={t("answerPhText")}
                    rows={4}
                    className="w-full resize-none rounded-2xl border-2 border-slate-200 bg-white px-4 py-3.5 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-primary disabled:opacity-60"
                  />
                  <button
                    type="button"
                    onClick={handleManualSubmit}
                    disabled={!canSubmit || submitting || !!result}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={15} />}
                    {t("submit")}
                  </button>
                </div>
              )}
            </div>
          </div>

          {result && (
            <div
              className={`border-t px-5 py-4 sm:px-7 ${
                result.is_correct ? "border-primary/20 bg-primary-soft/60" : "border-danger/20 bg-danger-soft/60"
              }`}
            >
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span
                  className={`inline-flex items-center gap-1.5 text-base font-extrabold ${
                    result.is_correct ? "text-primary" : "text-danger"
                  }`}
                >
                  {result.is_correct ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
                  {result.is_correct ? t("correct") : t("incorrect")}
                </span>
                {!result.is_correct && (
                  <span className="text-sm text-slate-700">
                    {t("correctAnswer")}:{" "}
                    <b className="font-mono">{formatAnswer(result.correct_answer)}</b>
                  </span>
                )}
                {result.elo_delta !== null && result.elo_delta !== undefined && (
                  <span className="text-sm font-bold tabular-nums text-ink">
                    {t("eloDelta", { delta: formatAnswer(result.elo_delta) })}
                  </span>
                )}
                {result.streak_days > 0 && (
                  <span className="inline-flex items-center gap-1 text-sm font-bold text-ink">
                    <Flame size={15} className="text-accent" />
                    {t("streak", { days: result.streak_days })}
                  </span>
                )}
                <span className="ml-auto text-xs font-medium text-muted">
                  {result.next_question ? t("nextQuestion") : t("resultsTitle")}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="mt-4">
          <HotkeyBar />
        </div>

        {isFreeMode && (
          <p className="mt-3 text-center text-xs text-muted">{t("hintNext")}</p>
        )}
      </div>
    </AuthGuard>
  );
}
