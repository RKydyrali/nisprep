import {
  clearToken,
  currentLocale,
  getToken,
  setChildId,
  setRole,
  setToken,
  setUser,
} from "./auth";

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isNetworkError(err: unknown): boolean {
  return err instanceof TypeError || (err instanceof ApiError && err.status === 0);
}

function redirectToLogin(): void {
  const locale = currentLocale();
  if (typeof window !== "undefined") {
    window.location.assign(`/${locale}/login`);
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (auth) {
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof TypeError) {
      throw new ApiError(0, "Network error", err);
    }
    throw err;
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (data.detail !== undefined) {
        detail = data.detail;
      }
    } catch {
      // non-JSON error body
    }

    if (res.status === 401) {
      // Редирект на вход уместен только для авторизованных запросов
      // (истёкший токен). Публичные эндпоинты (login-otp, request-otp,
      // register) должны просто показать ошибку, а не уводить со страницы.
      if (auth) {
        clearToken();
        redirectToLogin();
      }
      throw new ApiError(401, "Unauthorized", detail);
    }

    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? JSON.stringify(detail)
          : `HTTP ${res.status}`;

    throw new ApiError(res.status, message, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export type Language = "ru" | "kk";

export type SessionMode = "sprint" | "day1" | "day2" | "cat" | "free";
export type AnswerType = "integer" | "float" | "choice" | "text";
export type AnswerValue = number | string;

export interface MicroSkill {
  id: number;
  code: string;
  name_ru: string;
  name_kk: string;
}

export interface Question {
  session_id: string;
  question_id: number;
  template_id: number;
  micro_skill: MicroSkill;
  question_text: string;
  choices: string[] | null;
  answer_type: AnswerType;
  params: Record<string, unknown>;
  time_limit_sec: number;
  mode: string;
  total_questions: number;
  progress: number;
}

export interface SubmitPayload {
  session_id: string;
  template_id: number;
  params: Record<string, unknown>;
  answer: AnswerValue;
  time_taken_sec: number;
}

export interface SubmitResult {
  session_id: string;
  is_correct: boolean;
  correct_answer: AnswerValue | unknown;
  theta_after: number | null;
  elo_after: number | null;
  elo_delta: number | null;
  streak_days: number;
  streak_bonus: number | null;
  next_question: Question | null;
  session_finished: boolean;
}

export interface SessionState {
  session_id: string;
  mode: string;
  subject_code: string;
  asked: number[];
  question_idx: number;
  max_questions: number;
  answers: Record<string, unknown>[];
  ttl_remaining_sec: number;
}

export interface ParentUser {
  id: number;
  full_name: string;
  email: string | null;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  user: ParentUser | ChildUser | null;
  child: ChildUser | null;
}

export interface ChildUser {
  id: number;
  full_name: string;
  telegram_username: string;
  telegram_chat_id: number | null;
  is_verified: boolean;
  language: string;
  activation_code: string | null;
  current_elo: number;
  theta_math: number;
  theta_quant: number;
  theta_nat_sci: number;
  theta_lang: number;
  streak_days: number;
  total_solved: number;
  total_correct: number;
}

export interface ChildrenList {
  children: ChildUser[];
}

export interface OTPRequestResult {
  sent: boolean;
  need_activation: boolean;
  message: string | null;
}

export interface Readiness {
  psi: number;
  p_grant: number;
  band: "high" | "medium" | "low";
  theta: {
    math: number;
    quant: number;
    nat_sci: number;
    lang: number;
  };
  t_speed: number;
  weak_skills: WeakSkill[];
  graph: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  history: {
    dates: string[];
    series: {
      math: number[];
      quant: number[];
      nat_sci: number[];
      lang: number[];
    };
  };
}

export interface WeakSkill {
  micro_skill_id: number;
  name_ru: string;
  name_kk: string;
  code: string;
  accuracy: number;
  count: number;
  last_practiced_at: string | null;
}

export interface GraphNode {
  id: number;
  name_ru: string;
  name_kk: string;
  accuracy: number;
  weight: number;
}

export interface GraphEdge {
  from_id: number;
  to_id: number;
  value: number;
}

export interface ErrorLogQuestion {
  template_id: number;
  params: Record<string, unknown>;
  question_text: string;
  choices: string[] | null;
  correct_answer: AnswerValue | unknown;
  answer_type: AnswerType;
  difficulty_b: number;
  discrimination_a: number;
  micro_skill: MicroSkill | null;
}

export interface DueItem {
  item_id: number;
  review_number: number;
  ef: number;
  interval_days: number;
  next_review_at: string;
  wrong_count: number;
  question: ErrorLogQuestion;
}

export interface DueErrorLog {
  items: DueItem[];
}

export interface SessionStartResult extends Question {}

/* ---------------------------------- API calls ---------------------------------- */

export function registerParent(payload: {
  full_name: string;
  email: string;
  password: string;
}): Promise<TokenOut> {
  return request<TokenOut>("/auth/parent/register", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function loginParent(payload: {
  email: string;
  password: string;
}): Promise<TokenOut> {
  return request<TokenOut>("/auth/parent/login", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function listChildren(): Promise<ChildrenList> {
  return request<ChildrenList>("/auth/children");
}

export function createChild(payload: {
  full_name: string;
  telegram_username: string;
  password: string;
  language: Language;
}): Promise<ChildUser> {
  return request<ChildUser>("/auth/children", { method: "POST", body: payload });
}

export function updateChild(
  childId: number,
  payload: {
    full_name?: string;
    telegram_username?: string;
    password?: string;
    language?: Language;
  },
): Promise<ChildUser> {
  return request<ChildUser>(`/auth/children/${childId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function deleteChild(childId: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/auth/children/${childId}`, {
    method: "DELETE",
  });
}

export function requestOtp(telegram_username: string): Promise<OTPRequestResult> {
  return request<OTPRequestResult>("/auth/child/request-otp", {
    method: "POST",
    body: { telegram_username },
    auth: false,
  });
}

export function childLogin(payload: {
  telegram_username: string;
  password: string;
  otp: string;
}): Promise<TokenOut> {
  return request<TokenOut>("/auth/child/login-otp", {
    method: "POST",
    body: payload,
    auth: false,
  });
}

export function startSession(mode: SessionMode): Promise<SessionStartResult> {
  return request<SessionStartResult>("/session/start", {
    method: "POST",
    body: { mode },
  });
}

export function submitAnswer(payload: SubmitPayload): Promise<SubmitResult> {
  return request<SubmitResult>("/session/submit", {
    method: "POST",
    body: payload,
  });
}

export function getSessionState(sessionId: string): Promise<SessionState> {
  return request<SessionState>(`/session/state/${encodeURIComponent(sessionId)}`);
}

export function getReadiness(): Promise<Readiness> {
  return request<Readiness>("/analytics/readiness");
}

export function getParentReadiness(childId?: number): Promise<Readiness> {
  const query = childId !== undefined ? `?child_id=${childId}` : "";
  return request<Readiness>(`/analytics/parent/readiness${query}`);
}

export function getDueItems(): Promise<DueErrorLog> {
  return request<DueErrorLog>("/smart-error-log/due");
}

/** Отправка повторения из журнала ошибок (ревизия без активной сессии). */
export function submitRevision(payload: Omit<SubmitPayload, "session_id">): Promise<SubmitResult> {
  return submitAnswer({ ...payload, session_id: "revision" });
}

/* ------------------------------- session helpers ------------------------------- */

export function persistAuth(data: TokenOut): void {
  setToken(data.access_token);
  // Для входа ученика backend возвращает user = профиль родителя + child;
  // роль определяется наличием child.
  const role: "parent" | "child" = data.child ? "child" : "parent";
  setRole(role);
  setUser(data.user ?? null);
  if (data.child) {
    setChildId(data.child.id);
  }
}

export function choiceLabel(index: number): string {
  return String.fromCharCode(65 + index);
}
