"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { GraduationCap, Loader2 } from "lucide-react";
import { registerParent, persistAuth, isNetworkError } from "@/lib/api";

interface FormErrors {
  fullName?: string;
  email?: string;
  password?: string;
  confirm?: string;
  form?: string;
}

export default function RegisterPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("auth");
  const router = useRouter();
  const locale = params.locale;

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const next: FormErrors = {};
    if (fullName.trim().length < 2) next.fullName = t("errNameShort");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = t("errEmail");
    if (password.length < 6) next.password = t("errPasswordShort");
    if (confirm !== password) next.confirm = t("errPasswordMismatch");
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate() || submitting) return;

    setSubmitting(true);
    try {
      const data = await registerParent({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
      persistAuth(data);
      router.replace(`/${locale}/dashboard`);
    } catch (err) {
      if (isNetworkError(err)) {
        setErrors({ form: t("errNetwork") });
      } else {
        setErrors({ form: t("registerFailed") });
      }
      setSubmitting(false);
    }
  };

  const inputClass = (invalid?: string) =>
    `w-full rounded-2xl border bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-primary ${
      invalid ? "border-danger/70 focus:border-danger" : "border-slate-200 focus:ring-2 focus:ring-primary/20"
    }`;

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <div className="flex flex-col items-center text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-white shadow-md">
          <GraduationCap size={30} />
        </span>
        <h1 className="mt-4 text-2xl font-extrabold text-ink">{t("parentTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("parentSubtitle")}</p>
      </div>

      {errors.form && (
        <div className="mt-5 rounded-2xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm font-medium text-danger">
          {errors.form}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        <div>
          <label htmlFor="fullName" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("fullName")}
          </label>
          <input
            id="fullName"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder={t("fullNamePh")}
            className={inputClass(errors.fullName)}
            autoComplete="name"
          />
          {errors.fullName && (
            <p className="mt-1 text-xs font-medium text-danger">{errors.fullName}</p>
          )}
        </div>

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
            autoComplete="new-password"
          />
          {errors.password && (
            <p className="mt-1 text-xs font-medium text-danger">{errors.password}</p>
          )}
        </div>

        <div>
          <label htmlFor="confirm" className="mb-1.5 block text-sm font-semibold text-ink">
            {t("confirmPassword")}
          </label>
          <input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={t("passwordPh")}
            className={inputClass(errors.confirm)}
            autoComplete="new-password"
          />
          {errors.confirm && (
            <p className="mt-1 text-xs font-medium text-danger">{errors.confirm}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting && <Loader2 size={16} className="animate-spin" />}
          {t("createAccount")}
        </button>
      </form>

      <p className="mt-5 text-center text-sm text-muted">
        {t("toLogin")}{" "}
        <Link href={`/${locale}/login`} className="font-semibold text-primary hover:text-primary-hover">
          {t("loginBtn")}
        </Link>
      </p>
    </div>
  );
}
