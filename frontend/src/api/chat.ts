import { apiFetch, ApiError } from "./client";
import { pollJobStatus, type PollJobOptions } from "./jobs";
import { createSseStream, type SseStreamCallbacks } from "./sse";
import type { ChatRequest, ChatResponse, RawPost, SseTicketResponse } from "./types";

export async function sendChat(request: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(request),
    signal,
  });
}

export async function getSseTicket(streamKey?: string): Promise<string> {
  try {
    const endpoint = streamKey
      ? `/chat/ticket?stream_key=${encodeURIComponent(streamKey)}`
      : "/chat/ticket";
    const data = await apiFetch<SseTicketResponse>(endpoint);
    return data.ticket;
  } catch {
    return "";
  }
}

export interface SendChatResult {
  action: string;
  reply: string;
  session_id: string;
  posts?: RawPost[] | undefined;
  tokens_used?: number | null | undefined;
}

export async function sendChatStream(
  request: ChatRequest,
  callbacks: SseStreamCallbacks = {},
  signal?: AbortSignal
): Promise<SendChatResult> {
  const streamKey =
    request.stream_key ||
    request.session_id ||
    `stream-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

  // 1. Fetch SSE ticket in background
  const ticketPromise = getSseTicket(streamKey);

  // 2. Submit chat prompt
  const chatResponse = await sendChat(
    {
      ...request,
      stream_key: streamKey,
    },
    signal
  );

  // Instant response (inline actions like clarify, add_constraint, undo)
  if (chatResponse.status === "done") {
    return {
      action: chatResponse.action,
      reply: chatResponse.reply || "",
      session_id: chatResponse.session_id,
      tokens_used: chatResponse.tokens_used,
    };
  }

  // If async processing needed, connect to SSE stream with polling fallback
  if (chatResponse.status === "processing") {
    const ticket = await ticketPromise;

    try {
      // Connect to SSE stream backed by Redis Streams
      const sseResult = await createSseStream(
        {
          streamKey,
          ticket,
          signal,
        },
        callbacks
      );

      return {
        action: sseResult.action || chatResponse.action,
        reply: sseResult.reply || "",
        session_id: chatResponse.session_id,
        posts: sseResult.posts,
        tokens_used: sseResult.tokens_used ?? chatResponse.tokens_used,
      };
    } catch (sseErr: any) {
      if (signal?.aborted) {
        throw sseErr;
      }

      // If SSE fails due to proxy/network, seamlessly fall back to job status polling
      if (chatResponse.job_id) {
        callbacks.onStatus?.(
          {
            step: "generating",
            message: "Streaming connection switched to reliable polling channel...",
          },
          "fallback"
        );
        const jobResult = await pollJobStatus(chatResponse.job_id, { signal });
        return {
          action: jobResult.action || chatResponse.action,
          reply: jobResult.reply || "",
          session_id: chatResponse.session_id,
          tokens_used: chatResponse.tokens_used,
        };
      }
      throw sseErr;
    }
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

export async function sendChatAndWait(
  request: ChatRequest,
  options: PollJobOptions = {},
  signal?: AbortSignal
): Promise<SendChatResult> {
  const chatResponse = await sendChat(request, signal);

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

