"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  GraduationCap,
  Loader2,
  MessageCircle,
  Send,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { requestOtp, childLogin, persistAuth, isNetworkError, ApiError } from "@/lib/api";

const BOT_URL = "https://t.me/DanyshpanNis_bot";

interface FormErrors {
  username?: string;
  password?: string;
  otp?: string;
  form?: string;
}

export default function ChildLoginPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("auth");
  const router = useRouter();
  const locale = params.locale;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [otpRequested, setOtpRequested] = useState(false);
  const [needActivation, setNeedActivation] = useState(false);
  const [otpMessage, setOtpMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [requestingOtp, setRequestingOtp] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const normalizedUsername = username.trim().replace(/^@/, "");

  const handleRequestOtp = async () => {
    const next: FormErrors = {};
    if (normalizedUsername.length < 2) next.username = t("errNameShort");
    if (password.length < 1) next.password = t("errPasswordShort");
    setErrors(next);
    if (Object.keys(next).length > 0 || requestingOtp) return;

    setRequestingOtp(true);
    setErrors({});
    try {
      const result = await requestOtp(normalizedUsername);
      setOtpRequested(true);
      setNeedActivation(result.need_activation);
      setOtpMessage(result.message);
      if (result.need_activation) {
        setErrors({});
      }
    } catch (err) {
      if (isNetworkError(err)) {
        setErrors({ form: t("errNetwork") });
      } else {
        setErrors({ form: t("authFailed") });
      }
    } finally {
      setRequestingOtp(false);
    }
  };

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors = {};
    if (!otp.trim()) next.otp = t("errOtp");
    setErrors(next);
    if (Object.keys(next).length > 0 || submitting) return;

    setSubmitting(true);
    try {
      const data = await childLogin({
        telegram_username: normalizedUsername,
        password,
        otp: otp.trim(),
      });
      persistAuth(data);
      router.replace(`/${locale}/trainer`);
    } catch (err) {
      if (isNetworkError(err)) {
        setErrors({ form: t("errNetwork") });
      } else if (err instanceof ApiError && err.status === 403) {
        setErrors({ form: t("errActivation") });
        setNeedActivation(true);
      } else if (err instanceof ApiError && err.status === 401) {
        setErrors({ form: t("errInvalidCredentials") });
      } else if (err instanceof ApiError && err.status === 422) {
        setErrors({ otp: t("errOtpInvalid") });
      } else {
        setErrors({ form: t("authFailed") });
      }
      setSubmitting(false);
    }
  };

  const inputClass = (invalid?: string) =>
    `w-full rounded-2xl border bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 ${
      invalid ? "border-danger/70" : "border-slate-200 focus:border-primary focus:ring-2 focus:ring-primary/20"
    }`;

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <div className="flex flex-col items-center text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-white shadow-md">
          <GraduationCap size={30} />
        </span>
        <h1 className="mt-4 text-2xl font-extrabold text-ink">{t("childTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("childSubtitle")}</p>
      </div>

      {errors.form && (
        <div className="mt-5 rounded-2xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm font-medium text-danger">
          {errors.form}
        </div>
      )}

      {needActivation && (
        <div className="mt-5 rounded-2xl border border-accent/50 bg-accent-soft px-4 py-4">
          <p className="flex items-center gap-2 text-sm font-bold text-ink">
            <ShieldCheck size={16} className="text-accent" />
            {t("activationTitle")}
          </p>
          <ol className="mt-2 list-inside list-decimal space-y-1.5 text-sm text-slate-700">
            <li>
              {t("activationStep1")}{" "}
              <a
                href={BOT_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-primary underline"
              >
                @DanyshpanNis_bot
              </a>
            </li>
            <li>
              {t("activationStep2")}{" "}
              <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs font-bold text-primary">
                /verify &lt;код&gt;
              </code>
            </li>
            <li>{t("activationStep3")}</li>
            <li>{t("activationAfter")}</li>
          </ol>
        </div>
      )}

      {otpMessage && (
        <p className="mt-3 rounded-2xl border border-primary/30 bg-primary-soft px-4 py-2.5 text-sm font-medium text-primary">
          {otpMessage}
        </p>
      )}

      {!needActivation && (
        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
          <p className="flex items-center gap-1.5 font-semibold text-ink">
            <ShieldCheck size={13} className="text-accent" />
            {t("activationAlwaysTitle")}
          </p>
          <ol className="mt-1.5 list-inside list-decimal space-y-1">
            <li>
              {t("activationStep1")}{" "}
              <a
                href={BOT_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-primary underline"
              >
                @DanyshpanNis_bot
              </a>
            </li>
            <li>
              {t("activationStep2")}{" "}
              <code className="rounded bg-white px-1 py-0.5 font-mono text-[11px] font-bold text-primary">
                /verify &lt;код&gt;
              </code>
            </li>
            <li>{t("activationAfter")}</li>
          </ol>
        </div>
      )}

      <form onSubmit={handleLogin} className="mt-6 space-y-4" noValidate>
        <div>
          <label htmlFor="tg" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("telegramUsername")}
          </label>
          <input
            id="tg"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t("telegramUsernamePh")}
            className={inputClass(errors.username)}
            autoComplete="username"
          />
          {errors.username && (
            <p className="mt-1 text-xs font-medium text-danger">{errors.username}</p>
          )}
        </div>

        <div>
          <label htmlFor="pass" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("password")}
          </label>
          <input
            id="pass"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("passwordPh")}
            className={inputClass(errors.password)}
            autoComplete="current-password"
          />
          {errors.password && (
            <p className="mt-1 text-xs font-medium text-danger">{errors.password}</p>
          )}
        </div>

        {!otpRequested && (
          <button
            type="button"
            onClick={handleRequestOtp}
            disabled={requestingOtp}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {requestingOtp ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Send size={15} />
            )}
            {t("getCode")}
          </button>
        )}

        {otpRequested && (
          <>
            <button
              type="button"
              onClick={() => void handleRequestOtp()}
              disabled={requestingOtp}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-primary/30 bg-primary-soft px-5 py-2.5 text-xs font-bold text-primary transition-colors hover:bg-primary/10 disabled:opacity-60"
            >
              {requestingOtp ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Send size={13} />
              )}
              {t("resendCode")}
            </button>
            <div>
              <label htmlFor="otp" className="mb-1.5 block text-sm font-semibold text-ink">
                {t("otp")}
              </label>
              <input
                id="otp"
                type="text"
                inputMode="numeric"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder={t("otpPh")}
                className={`${inputClass(errors.otp)} text-center font-mono text-lg tracking-[0.4em]`}
                autoComplete="one-time-code"
              />
              <p className="mt-1 flex items-center gap-1 text-xs text-muted">
                <MessageCircle size={12} className="text-primary" />
                {t("otpHint")}
              </p>
              {errors.otp && <p className="mt-1 text-xs font-medium text-danger">{errors.otp}</p>}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
              {t("loginOtpBtn")}
            </button>
          </>
        )}
      </form>

      <p className="mt-5 text-center text-sm text-muted">
        <Link
          href={`/${locale}/login`}
          className="inline-flex items-center gap-1.5 font-semibold text-primary hover:text-primary-hover"
        >
          <UserRound size={14} />
          {t("backToParent")}
        </Link>
      </p>
    </div>
  );
}
