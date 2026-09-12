import { apiFetch, clearToken, setToken } from "./client";
import type {
  GoogleUrlResponse,
  GoogleVerifyRequest,
  LoginRequest,
  MeResponse,
  SignupRequest,
  TokenResponse,
} from "./types";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  const token = data.access_token || data.token;
  if (token) {
    setToken(token);
  }
  return data;
}

export async function signup(credentials: SignupRequest): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  const token = data.access_token || data.token;
  if (token) {
    setToken(token);
  }
  return data;
}

export async function googleVerify(credential: string): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/google/verify", {
    method: "POST",
    body: JSON.stringify({ credential } as GoogleVerifyRequest),
  });
  const token = data.access_token || data.token;
  if (token) {
    setToken(token);
  }
  return data;
}

export async function getGoogleLoginUrl(): Promise<string> {
  const data = await apiFetch<GoogleUrlResponse>("/auth/google/url", {
    method: "GET",
  });
  return data.url;
}

export async function refreshSession(): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
  });
  const token = data.access_token || data.token;
  if (token) {
    setToken(token);
  }
  return data;
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me", {
    method: "GET",
  });
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/auth/logout", {
      method: "POST",
    });
  } catch {
    // Non-fatal, clear local state anyway
  } finally {
    clearToken();
  }
}

// 12-minute silent token refresh scheduler (token lifetime is 15 minutes)
let _refreshTimer: NodeJS.Timeout | null = null;

export function startAutoTokenRefresh(): void {
  if (typeof window === "undefined") return;
  if (_refreshTimer) clearInterval(_refreshTimer);

  _refreshTimer = setInterval(async () => {
    try {
      await refreshSession();
    } catch {
      stopAutoTokenRefresh();
    }
  }, 12 * 60 * 1000);
}

export function stopAutoTokenRefresh(): void {
  if (_refreshTimer) {
    clearInterval(_refreshTimer);
    _refreshTimer = null;
  }
}

