import { apiFetch, ApiError } from "./client";
import { pollJobStatus, type PollJobOptions } from "./jobs";
import type { ChatRequest, ChatResponse } from "./types";

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export interface SendChatResult {
  action: string;
  reply: string;
  session_id: string;
  tokens_used?: number | null;
}

export async function sendChatAndWait(
  request: ChatRequest,
  options: PollJobOptions = {}
): Promise<SendChatResult> {
  const chatResponse = await sendChat(request);

  if (chatResponse.status === "done") {
    return {
      action: chatResponse.action,
      reply: chatResponse.reply || "",
      session_id: chatResponse.session_id,
      tokens_used: chatResponse.tokens_used,
    };
  }

  if (chatResponse.status === "processing" && chatResponse.job_id) {
    const jobResult = await pollJobStatus(chatResponse.job_id, options);
    return {
      action: jobResult.action || chatResponse.action,
      reply: jobResult.reply || "",
      session_id: chatResponse.session_id,
      tokens_used: chatResponse.tokens_used,
    };
  }

  if (chatResponse.status === "error") {
    throw new ApiError(500, chatResponse.reply || "Failed to process chat request", "chat_error");
  }

  return {
    action: chatResponse.action || "unknown",
    reply: chatResponse.reply || "",
    session_id: chatResponse.session_id,
    tokens_used: chatResponse.tokens_used,
  };
}
