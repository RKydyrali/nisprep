"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { GraduationCap, LogOut, Menu, X } from "lucide-react";
import { clearToken, currentLocale, getRole } from "@/lib/auth";
import { useOfflineSync } from "@/lib/offline-sync";
import { WifiOff } from "lucide-react";

function LocaleSwitch({ locale }: { locale: string }) {
  const pathname = usePathname();
  const target = pathname.replace(/^\/(ru|kk)/, locale === "ru" ? "/kk" : "/ru");
  const isRu = locale === "ru";

  return (
    <Link
      href={target}
      hrefLang={isRu ? "kk" : "ru"}
      className="flex items-center gap-0.5 rounded-full border border-slate-200 bg-white px-1 py-0.5 text-xs font-semibold shadow-sm"
      aria-label={isRu ? "Қазақша" : "Русский"}
    >
      <span
        className={`rounded-full px-2 py-1 transition-colors ${
          isRu ? "bg-primary text-white" : "text-muted hover:text-ink"
        }`}
      >
        РУ
      </span>
      <span
        className={`rounded-full px-2 py-1 transition-colors ${
          !isRu ? "bg-primary text-white" : "text-muted hover:text-ink"
        }`}
      >
        ҚАЗ
      </span>
    </Link>
  );
}

export default function Header() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  const locale = currentLocale();
  const role = getRole();
  const { isOnline } = useOfflineSync();

  const isActive = (href: string) =>
    pathname === `/${locale}${href}` || pathname === href;

  const links: { href: string; label: string; active?: boolean }[] = [];

  if (role === "parent") {
    links.push({ href: "/dashboard", label: t("dashboard") });
  } else if (role === "child") {
    links.push({ href: "/trainer", label: t("trainer") });
    links.push({ href: "/analytics", label: t("analytics") });
    links.push({ href: "/error-log", label: t("errorLog") });
  } else {
    links.push({ href: "/login", label: t("login") });
    links.push({ href: "/register", label: t("register") });
  }

  const handleLogout = () => {
    clearToken();
    setMenuOpen(false);
    router.replace(`/${locale}/`);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-surface/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link
          href={`/${locale}`}
          className="flex items-center gap-2.5 font-extrabold tracking-tight text-ink"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white shadow-sm">
            <GraduationCap size={22} />
          </span>
          <span className="text-lg">
            {t("brand")}
            <span className="hidden text-xs font-semibold text-muted sm:inline">
              {" "}
              · {t("brandFull")}
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={`/${locale}${link.href}`}
              className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                isActive(link.href)
                  ? "bg-primary-soft text-primary"
                  : "text-slate-600 hover:bg-slate-100 hover:text-ink"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {!isOnline && (
            <span className="flex items-center gap-1 rounded-full bg-danger-soft px-2.5 py-1 text-xs font-semibold text-danger">
              <WifiOff size={12} />
              offline
            </span>
          )}
          <LocaleSwitch locale={locale} />
          {role && (
            <button
              type="button"
              onClick={handleLogout}
              className="hidden items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:border-danger/40 hover:text-danger md:flex"
            >
              <LogOut size={14} />
              {t("logout")}
            </button>
          )}
          <button
            type="button"
            aria-label="Menu"
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded-full p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav className="border-t border-slate-200/70 bg-white px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={`/${locale}${link.href}`}
                onClick={() => setMenuOpen(false)}
                className={`rounded-xl px-3 py-2.5 text-sm font-medium ${
                  isActive(link.href)
                    ? "bg-primary-soft text-primary"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {link.label}
              </Link>
            ))}
            {role && (
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-danger hover:bg-danger-soft"
              >
                <LogOut size={15} />
                {t("logout")}
              </button>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
