/**
 * frontend/src/api/images.ts — Image Generation Subsystem API Client
 */

import { apiFetch, ApiError } from "./client";
import type {
  ImageGenerateRequest,
  BatchImageGenerateRequest,
  ImageJobResponse,
  BatchImageJobResponse,
  ImageJobStatusResponse,
  ImageAssetMeta,
  VisualProfileResponse,
  VisualProfileCreateRequest,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

/**
 * Return direct URL to stream raw PNG/JPEG bytes from backend asset storage.
 */
export function getImageUrl(assetId: string): string {
  if (!assetId) return "";
  // If it's already an absolute URL or data URI, return as-is
  if (assetId.startsWith("http://") || assetId.startsWith("https://") || assetId.startsWith("data:")) {
    return assetId;
  }
  return `${BASE_URL}/images/${assetId}`;
}

/**
 * Trigger background image generation for a single post. Returns job_id to poll.
 */
export async function generateImage(req: ImageGenerateRequest): Promise<ImageJobResponse> {
  return apiFetch<ImageJobResponse>("/images/generate", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * Trigger background batch image generation for all posts in a session.
 */
export async function generateBatchImages(req: BatchImageGenerateRequest): Promise<BatchImageJobResponse> {
  return apiFetch<BatchImageJobResponse>("/images/generate-batch", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * Check status of an in-flight image generation job.
 */
export async function getImageJobStatus(jobId: string): Promise<ImageJobStatusResponse> {
  return apiFetch<ImageJobStatusResponse>(`/images/status/${jobId}`, {
    method: "GET",
  });
}

/**
 * Retrieve metadata for a completed image asset.
 */
export async function getImageMeta(assetId: string): Promise<ImageAssetMeta> {
  return apiFetch<ImageAssetMeta>(`/images/${assetId}/meta`, {
    method: "GET",
  });
}

/**
 * List brand visual profiles available to the current user.
 */
export async function listVisualProfiles(): Promise<VisualProfileResponse[]> {
  return apiFetch<VisualProfileResponse[]>("/images/profiles/list", {
    method: "GET",
  });
}

/**
 * Create a new custom brand visual profile.
 */
export async function createVisualProfile(req: VisualProfileCreateRequest): Promise<VisualProfileResponse> {
  return apiFetch<VisualProfileResponse>("/images/profiles/create", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * Poll image job status until completed or failed.
 *
 * @param jobId The RQ job ID returned by generateImage
 * @param onProgress Optional callback on status poll tick
 * @param timeoutMs Max wait time in ms (default 120,000ms = 2 mins)
 * @param intervalMs Poll interval (default 1,500ms)
 */
export async function pollImageJob(
  jobId: string,
  onProgress?: (status: ImageJobStatusResponse) => void,
  timeoutMs = 120000,
  intervalMs = 1500
): Promise<ImageJobStatusResponse> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const status = await getImageJobStatus(jobId);
    if (onProgress) onProgress(status);

    if (status.status === "completed") {
      return status;
    }

    if (status.status === "failed") {
      throw new ApiError(500, status.error || "Image generation failed on worker", "image_generation_failed");
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new ApiError(408, "Image generation timed out waiting for worker", "image_job_timeout");
}
