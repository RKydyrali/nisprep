import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { routing, type Locale } from "@/i18n/routing";
import Header from "@/components/Header";
import { ToastProvider } from "@/components/Toast";
import "../globals.css";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: { locale: string };
}): Promise<Metadata> {
  const locale = (routing.locales.includes(params.locale as Locale)
    ? params.locale
    : routing.defaultLocale) as Locale;
  const t = await getTranslations({ locale, namespace: "nav" });
  return {
    title: t("brandFull"),
    description:
      locale === "kk"
        ? "НИШ-ке бейімделген дайындық платформасы: CAT тесті, ақылды қателер журналы, «Өркен» грантына дайындық аналитикасы."
        : "Адаптивная платформа подготовки к НИШ: тест CAT, умный журнал ошибок, аналитика готовности к гранту «Өркен».",
    manifest: "/manifest.json",
    icons: {
      icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    },
    openGraph: {
      title: t("brandFull"),
      description:
        locale === "kk"
          ? "НИШ-ке бейімделген дайындық платформасы"
          : "Адаптивная платформа подготовки к НИШ",
      locale,
      type: "website",
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#047857",
  colorScheme: "light",
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const { locale } = params;

  if (!routing.locales.includes(locale as Locale)) {
    notFound();
  }

  setRequestLocale(locale);

  const messages = await getMessages();

  return (
    <html lang={locale} className={inter.variable}>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#047857" />
      </head>
      <body className="min-h-screen bg-surface font-sans text-ink">
        <NextIntlClientProvider messages={messages}>
          <ToastProvider>
            <Header />
            <main className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6">{children}</main>
          </ToastProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
