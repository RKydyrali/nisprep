"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Loader2, PlusCircle, RefreshCw, UserPlus } from "lucide-react";
import AuthGuard from "@/components/AuthGuard";
import ChildCard from "@/components/ChildCard";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import {
  listChildren,
  createChild,
  updateChild,
  deleteChild,
  getParentReadiness,
  isNetworkError,
  type ChildUser,
  type Readiness,
  type Language,
} from "@/lib/api";

const BOT_URL = "https://t.me/DanyshpanNis_bot";

type FormMode = "create" | "edit";

interface ChildFormState {
  fullName: string;
  tgUsername: string;
  password: string;
  language: Language;
}

const EMPTY_FORM: ChildFormState = {
  fullName: "",
  tgUsername: "",
  password: "",
  language: "ru",
};

export default function DashboardPage({
  params,
}: {
  params: { locale: string };
}) {
  const t = useTranslations("dashboard");
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const { toast } = useToast();
  const locale = params.locale;

  const [children, setChildren] = useState<ChildUser[]>([]);
  const [readinessMap, setReadinessMap] = useState<Record<number, Readiness>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>("create");
  const [editingChild, setEditingChild] = useState<ChildUser | null>(null);
  const [form, setForm] = useState<ChildFormState>(EMPTY_FORM);
  const [formSaving, setFormSaving] = useState(false);

  const [activationChild, setActivationChild] = useState<ChildUser | null>(null);
  const [deleting, setDeleting] = useState<ChildUser | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const data = await listChildren();
      setChildren(data.children);
      const map: Record<number, Readiness> = {};
      await Promise.allSettled(
        data.children.map(async (child) => {
          try {
            map[child.id] = await getParentReadiness(child.id);
          } catch {
            // аналитика недоступна — карточка просто без спарклайна
          }
        }),
      );
      setReadinessMap(map);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    setFormMode("create");
    setEditingChild(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const openEdit = (child: ChildUser) => {
    setFormMode("edit");
    setEditingChild(child);
    setForm({
      fullName: child.full_name,
      tgUsername: child.telegram_username,
      password: "",
      language: (child.language === "kk" ? "kk" : "ru") as Language,
    });
    setFormOpen(true);
  };

  const handleFormSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (formSaving) return;

    const name = form.fullName.trim();
    const tg = form.tgUsername.trim().replace(/^@/, "");

    if (name.length < 2 || tg.length < 2) {
      toast(tc("error"), "error");
      return;
    }
    if (formMode === "create" && form.password.length < 6) {
      toast(tc("error"), "error");
      return;
    }

    setFormSaving(true);
    try {
      if (formMode === "create") {
        const created = await createChild({
          full_name: name,
          telegram_username: tg,
          password: form.password,
          language: form.language,
        });
        setChildren((prev) => [...prev, created]);
        setFormOpen(false);
        toast(t("created"), "success");
        setActivationChild(created);
      } else if (editingChild) {
        const updated = await updateChild(editingChild.id, {
          full_name: name,
          telegram_username: tg,
          ...(form.password ? { password: form.password } : {}),
          language: form.language,
        });
        setChildren((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        setFormOpen(false);
        toast(t("updated"), "success");
      }
    } catch (err) {
      toast(isNetworkError(err) ? ta("errNetwork") : tc("error"), "error");
    } finally {
      setFormSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    try {
      await deleteChild(deleting.id);
      setChildren((prev) => prev.filter((c) => c.id !== deleting.id));
      setDeleting(null);
      toast(t("deleted"), "success");
    } catch {
      setDeleting(null);
      toast(t("deleteError"), "error");
    }
  };

  const inputClass =
    "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-ink shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20";

  return (
    <AuthGuard role="parent">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-ink sm:text-3xl">
            {t("title")}
          </h1>
          <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
        >
          <PlusCircle size={17} />
          {t("addChild")}
        </button>
      </div>

      <div className="mt-6">
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
        ) : children.length === 0 ? (
          <div className="flex flex-col items-center gap-4 rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-soft text-primary">
              <UserPlus size={30} />
            </span>
            <p className="max-w-sm text-sm text-muted">{t("noChildren")}</p>
            <button
              type="button"
              onClick={openCreate}
              className="inline-flex items-center gap-2 rounded-2xl bg-primary px-5 py-3 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
            >
              <PlusCircle size={16} />
              {t("addChild")}
            </button>
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {children.map((child) => (
              <ChildCard
                key={child.id}
                child={child}
                locale={locale}
                readiness={readinessMap[child.id] ?? null}
                onEdit={openEdit}
                onDelete={setDeleting}
              />
            ))}
          </div>
        )}
      </div>

      {/* Создание / редактирование ученика */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={formMode === "create" ? t("addChildTitle") : t("edit")}
      >
        <form onSubmit={handleFormSubmit} className="space-y-4">
          <div>
            <label htmlFor="cf-name" className="mb-1.5 block text-sm font-semibold text-ink">
              {t("childName")}
            </label>
            <input
              id="cf-name"
              type="text"
              value={form.fullName}
              onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))}
              placeholder={t("childNamePh")}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="cf-tg" className="mb-1.5 block text-sm font-semibold text-ink">
              {t("tgUsername")}
            </label>
            <input
              id="cf-tg"
              type="text"
              value={form.tgUsername}
              onChange={(e) => setForm((f) => ({ ...f, tgUsername: e.target.value }))}
              placeholder={t("tgUsernamePh")}
              className={inputClass}
              autoComplete="off"
            />
          </div>
          <div>
            <label htmlFor="cf-pass" className="mb-1.5 block text-sm font-semibold text-ink">
              {t("childPassword")}
            </label>
            <input
              id="cf-pass"
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder={
                formMode === "edit" ? "••••••" : t("childPasswordPh")
              }
              className={inputClass}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label htmlFor="cf-lang" className="mb-1.5 block text-sm font-semibold text-ink">
              {t("language")}
            </label>
            <select
              id="cf-lang"
              value={form.language}
              onChange={(e) => setForm((f) => ({ ...f, language: e.target.value as Language }))}
              className={inputClass}
            >
              <option value="ru">{t("langRu")}</option>
              <option value="kk">{t("langKk")}</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={formSaving}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-5 py-3.5 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {formSaving && <Loader2 size={16} className="animate-spin" />}
            {formMode === "create" ? t("create") : t("editing")}
          </button>
        </form>
      </Modal>

      {/* Код активации — показывается один раз */}
      <Modal
        open={activationChild !== null}
        onClose={() => setActivationChild(null)}
        title={t("activationTitle")}
      >
        {activationChild && (
          <div className="space-y-4 text-center">
            <p className="text-sm text-muted">{t("activationDesc")}</p>
            <div className="mx-auto w-fit rounded-2xl border-2 border-dashed border-accent/60 bg-accent-soft px-8 py-5">
              <span className="font-mono text-3xl font-extrabold tracking-[0.3em] text-ink">
                {activationChild.activation_code ?? "—"}
              </span>
            </div>
            <a
              href={BOT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-2xl bg-primary px-6 py-3 text-sm font-bold text-white shadow-md transition-colors hover:bg-primary-hover"
            >
              {t("activationBot")}
              <span aria-hidden>→</span>
            </a>
            <p className="text-xs text-muted">{t("activationHint")}</p>
          </div>
        )}
      </Modal>

      {/* Подтверждение удаления */}
      <Modal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={t("delete")}
      >
        {deleting && (
          <div className="space-y-5">
            <p className="text-sm leading-relaxed text-slate-700">
              {t("deleteConfirm", { name: deleting.full_name })}
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setDeleting(null)}
                className="flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
              >
                {t("cancel")}
              </button>
              <button
                type="button"
                onClick={() => void handleDelete()}
                className="flex-1 rounded-2xl bg-danger px-4 py-3 text-sm font-bold text-white shadow-md hover:bg-red-700"
              >
                {t("delete")}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </AuthGuard>
  );
}
