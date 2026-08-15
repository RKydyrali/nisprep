"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { GraduationCap, Loader2, UserRound } from "lucide-react";
import { loginParent, persistAuth, isNetworkError } from "@/lib/api";

interface FormErrors {
  email?: string;
  password?: string;
  form?: string;
}

export default function LoginPage({ params }: { params: { locale: string } }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const locale = params.locale;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const next: FormErrors = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = t("errEmail");
    if (!password) next.password = t("errPasswordShort");
    setErrors(next);
    if (Object.keys(next).length > 0 || submitting) return;

    setSubmitting(true);
    try {
      const data = await loginParent({ email: email.trim(), password });
      persistAuth(data);
      router.replace(`/${locale}/dashboard`);
    } catch (err) {
      if (isNetworkError(err)) {
        setErrors({ form: t("errNetwork") });
      } else if (err instanceof Error && err.message.includes("401")) {
        setErrors({ form: t("errInvalidCredentials") });
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
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-white shadow-md">
          <GraduationCap size={30} />
        </span>
        <h1 className="mt-4 text-2xl font-extrabold text-ink">{t("parentLoginTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("parentLoginSubtitle")}</p>
      </div>

      {errors.form && (
        <div className="mt-5 rounded-2xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm font-medium text-danger">
          {errors.form}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("email")}
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPh")}
            className={inputClass(errors.email)}
            autoComplete="email"
          />
          {errors.email && <p className="mt-1 text-xs font-medium text-danger">{errors.email}</p>}
        </div>

        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("password")}
          </label>
          <input
            id="password"
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

        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting && <Loader2 size={16} className="animate-spin" />}
          {t("loginBtn")}
        </button>
      </form>

      <div className="mt-5 space-y-2 text-center text-sm">
        <p className="text-muted">
          {t("toRegister")}{" "}
          <Link
            href={`/${locale}/register`}
            className="font-semibold text-primary hover:text-primary-hover"
          >
            {t("createAccount")}
          </Link>
        </p>
        <Link
          href={`/${locale}/child-login`}
          className="inline-flex items-center gap-1.5 font-semibold text-accent hover:text-amber-600"
        >
          <UserRound size={14} />
          {t("childLoginLink")}
        </Link>
      </div>
    </div>
  );
}
