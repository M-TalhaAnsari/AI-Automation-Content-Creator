/**
 * frontend/src/api/sse.ts — Production-grade Server-Sent Events (SSE) Client
 * with Last-Event-ID reconnect, ticket/Bearer auth, and pipeline state dispatch.
 */
import { BASE_URL, getAnonId, getToken } from "./client";
import type { SseDonePayload, SseErrorPayload, SseStatusPayload } from "./types";

export interface SseStreamCallbacks {
  onStatus?: (status: SseStatusPayload, eventId: string) => void;
  onDone?: (result: SseDonePayload, eventId: string) => void;
  onError?: (error: SseErrorPayload, eventId: string) => void;
}

export interface SseStreamOptions {
  streamKey: string;
  ticket?: string | undefined;
  signal?: AbortSignal | undefined;
  maxReconnectAttempts?: number | undefined;
}

export async function createSseStream(
  options: SseStreamOptions,
  callbacks: SseStreamCallbacks
): Promise<SseDonePayload> {
  const { streamKey, ticket, signal, maxReconnectAttempts = 3 } = options;
  let lastEventId = "";
  let reconnectAttempts = 0;

  return new Promise<SseDonePayload>((resolve, reject) => {
    async function connect() {
      if (signal?.aborted) {
        reject(new Error("Stream connection cancelled by user"));
        return;
      }

      // Build streaming URL with optional single-use ticket
      const url = new URL(`${BASE_URL}/chat/stream/${encodeURIComponent(streamKey)}`);
      if (ticket) {
        url.searchParams.set("ticket", ticket);
      }

      const headers: Record<string, string> = {
        Accept: "text/event-stream",
      };

      const token = getToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        headers["X-Anon-Id"] = getAnonId();
      }

      if (lastEventId) {
        headers["Last-Event-ID"] = lastEventId;
      }

      try {
        const response = await fetch(url.toString(), {
          method: "GET",
          headers,
          credentials: "include",
          signal: signal ?? null,
        });

        if (!response.ok) {
          const errorText = await response.text().catch(() => "Stream connection failed");
          throw new Error(`SSE error (${response.status}): ${errorText}`);
        }

        if (!response.body) {
          throw new Error("ReadableStream not supported by browser");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let currentEvent = "message";
        let currentId = "";
        let currentData = "";

        while (true) {
          if (signal?.aborted) {
            reader.cancel();
            reject(new Error("Generation stopped by user"));
            return;
          }

          const { value, done } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split(/\r?\n/);
          // Keep uncompleted partial line in buffer
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith(":")) {
              // Heartbeat comment, ignore
              continue;
            }

            if (line.startsWith("id:")) {
              currentId = line.slice(3).trim();
              lastEventId = currentId;
            } else if (line.startsWith("event:")) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              currentData += (currentData ? "\n" : "") + line.slice(5).trim();
            } else if (line === "") {
              // Dispatch event on empty line delimiter
              if (currentData) {
                try {
                  const parsed = JSON.parse(currentData);

                  if (currentEvent === "status") {
                    callbacks.onStatus?.(parsed as SseStatusPayload, currentId);
                  } else if (currentEvent === "done") {
                    const doneResult = parsed as SseDonePayload;
                    callbacks.onDone?.(doneResult, currentId);
                    resolve(doneResult);
                    return;
                  } else if (currentEvent === "error") {
                    const errPayload = parsed as SseErrorPayload;
                    callbacks.onError?.(errPayload, currentId);
                    reject(new Error(errPayload.detail || "Generation error"));
                    return;
                  }
                } catch {
                  // Ignore JSON parse errors for non-JSON SSE data
                }
              }
              // Reset for next event
              currentEvent = "message";
              currentData = "";
            }
          }
        }
      } catch (err: any) {
        if (signal?.aborted) {
          reject(new Error("Generation stopped by user"));
          return;
        }

        // Reconnect with Last-Event-ID if stream unexpectedly disconnected
        if (reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const backoffDelay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 4000);
          setTimeout(connect, backoffDelay);
        } else {
          reject(err);
        }
      }
    }

    connect();
  });
}
