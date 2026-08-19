import { apiFetch, ApiError } from "./client";
import type { JobStatusResponse } from "./types";

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/chat/status/${encodeURIComponent(jobId)}`, {
    method: "GET",
  });
}

export interface PollJobOptions {
  onProgress?: (status: string, attempt: number) => void;
  intervalMs?: number;
  maxAttempts?: number;
  signal?: AbortSignal;
}

export async function pollJobStatus(jobId: string, options: PollJobOptions = {}): Promise<JobStatusResponse> {
  const intervalMs = options.intervalMs ?? 1500;
  const maxAttempts = options.maxAttempts ?? 120; // 120 * 1.5s = 3 minutes max

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    if (options.signal?.aborted) {
      throw new ApiError(0, "Job polling was canceled", "aborted");
    }

    const response = await getJobStatus(jobId);
    if (options.onProgress) {
      options.onProgress(response.status, attempt);
    }

    if (response.status === "done") {
      return response;
    }

    if (response.status === "error") {
      throw new ApiError(
        500,
        response.detail || "Background generation failed. Please check server logs or retry with another prompt.",
        "job_failed"
      );
    }

    // Wait before next poll attempt
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new ApiError(408, "Content generation timed out while waiting for worker.", "timeout");
}
