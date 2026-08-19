import { apiFetch, clearToken, setToken } from "./client";
import type { LoginRequest, MeResponse, SignupRequest, TokenResponse } from "./types";

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (data.token) {
    setToken(data.token);
  }
  return data;
}

export async function signup(credentials: SignupRequest): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (data.token) {
    setToken(data.token);
  }
  return data;
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me", {
    method: "GET",
  });
}

export function logout(): void {
  clearToken();
}
