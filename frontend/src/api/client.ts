import type { ApiErrorDetail } from "./types";

const BASE_URL = ((import.meta.env["VITE_API_URL"] as string) || "http://127.0.0.1:8000").replace(/\/+$/, "");

const TOKEN_KEY = "trendforge_jwt_token";
const ANON_ID_KEY = "trendforge_anon_id";

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  retryAfterSeconds: number;

  constructor(status: number, message: string, code = "error", detail = "", retryAfterSeconds = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export function clearToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function isLoggedIn(): boolean {
  return Boolean(getToken());
}

export function getAnonId(): string {
  if (typeof window === "undefined") return "guest-default-id";
  let anonId = localStorage.getItem(ANON_ID_KEY);
  if (!anonId) {
    anonId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `anon-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    localStorage.setItem(ANON_ID_KEY, anonId);
  }
  return anonId;
}

export interface FetchOptions extends Omit<RequestInit, "signal"> {
  timeoutMs?: number | undefined;
  signal?: AbortSignal | null | undefined;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  const token = getToken();
  const anonId = getAnonId();

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.set("X-Anon-Id", anonId);
  }

  const timeoutMs = options.timeoutMs ?? 30000;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let detail = "";
      let code = "error";
      let retryAfterSeconds = 0;

      const retryHeader = response.headers.get("Retry-After");
      if (retryHeader) {
        retryAfterSeconds = parseInt(retryHeader, 10) || 5;
      }

      try {
        const errorData: ApiErrorDetail = await response.json();
        if (typeof errorData.detail === "string") {
          detail = errorData.detail;
          if (detail === "signup_required") {
            code = "signup_required";
          }
        } else if (Array.isArray(errorData.detail)) {
          detail = errorData.detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
        } else if (errorData.message) {
          detail = errorData.message;
        }
      } catch {
        detail = await response.text().catch(() => response.statusText);
      }

      if (response.status === 401) {
        code = "unauthorized";
        if (token) {
          clearToken();
        }
      } else if (response.status === 403 && detail === "signup_required") {
        code = "signup_required";
      } else if (response.status === 429) {
        code = "rate_limited";
        if (!retryAfterSeconds) retryAfterSeconds = 10;
      }

      throw new ApiError(
        response.status,
        detail || `Request failed with status ${response.status}`,
        code,
        detail,
        retryAfterSeconds
      );
    }

    // Return empty object for 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      if (options.signal?.aborted) {
        throw new ApiError(499, "Generation stopped by user.", "cancelled");
      }
      throw new ApiError(408, "Request timed out. Please try again.", "timeout");
    }

    throw new ApiError(
      0,
      error instanceof Error ? error.message : "Network error. Please ensure the backend is running.",
      "network_error"
    );
  }
}
