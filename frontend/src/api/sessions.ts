import { apiFetch } from "./client";
import type { SessionListItem, SessionView } from "./types";

export async function listSessions(): Promise<SessionListItem[]> {
  return apiFetch<SessionListItem[]>("/sessions", {
    method: "GET",
  });
}

export async function getSession(sessionId: string): Promise<SessionView> {
  return apiFetch<SessionView>(`/session/${encodeURIComponent(sessionId)}`, {
    method: "GET",
  });
}

export async function deleteSession(sessionId: string): Promise<{ status: string; session_id: string }> {
  return apiFetch<{ status: string; session_id: string }>(`/session/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}
