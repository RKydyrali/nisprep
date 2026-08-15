import { setRequestLocale } from "next-intl/server";
import type { Locale } from "@/i18n/routing";

export default function AuthLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const { locale } = params;
  if (["ru", "kk"].includes(locale)) {
    setRequestLocale(locale as Locale);
  }
  return (
    <div className="flex min-h-[calc(100vh-7rem)] items-center justify-center py-8">
      <div className="w-full max-w-md animate-fade-in-up">{children}</div>
    </div>
  );
}
