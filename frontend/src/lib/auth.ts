const TOKEN_KEY = "danyshpan_token";
const ROLE_KEY = "danyshpan_role";
const USER_KEY = "danyshpan_user";
const CHILD_ID_KEY = "danyshpan_child_id";

export type UserRole = "parent" | "child";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.localStorage.removeItem(CHILD_ID_KEY);
}

export function getRole(): UserRole | null {
  if (typeof window === "undefined") return null;
  const role = window.localStorage.getItem(ROLE_KEY);
  return role === "parent" || role === "child" ? role : null;
}

export function setRole(role: UserRole): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ROLE_KEY, role);
}

export function getUser<T = unknown>(): T | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function setUser<T>(user: T): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getChildId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(CHILD_ID_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

export function setChildId(id: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CHILD_ID_KEY, String(id));
}

export function isParent(): boolean {
  return getRole() === "parent";
}

export function isChild(): boolean {
  return getRole() === "child";
}

export function currentLocale(): string {
  if (typeof window === "undefined") return "ru";
  const path = window.location.pathname;
  if (path.startsWith("/kk")) return "kk";
  return "ru";
}

export function loginRedirectPath(): string {
  const locale = currentLocale();
  return `/${locale}/login`;
}
