"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { clearToken, getRole, currentLocale, type UserRole } from "@/lib/auth";
import { Loader2 } from "lucide-react";

interface AuthGuardProps {
  role: UserRole;
  children: ReactNode;
}

/**
 * Проверяет наличие токена и роль; при отсутствии — редирект на вход.
 */
export default function AuthGuard({ role, children }: AuthGuardProps) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const current = getRole();
    if (!current) {
      clearToken();
      router.replace(`/${currentLocale()}/login`);
      return;
    }
    if (current !== role) {
      router.replace(`/${currentLocale()}/${current === "parent" ? "dashboard" : "trainer"}`);
      return;
    }
    setReady(true);
  }, [role, router]);

  if (!ready) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 size={28} className="animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
