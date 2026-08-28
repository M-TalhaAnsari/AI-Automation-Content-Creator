/**
 * frontend/src/api/types.ts — API Data Contracts matching FastAPI Backend Pydantic Models
 */

export interface SignupRequest {
  name?: string | undefined;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  token: string;
}

export interface MeResponse {
  id: number;
  name?: string | undefined;
  email: string;
  tier?: string | undefined;
}

export interface SessionListItem {
  session_id: string;
  title: string | null;
  created_at: string;
  last_active_at: string;
}

export interface RawPost {
  number?: number | undefined;
  title: string;
  hook: string;
  summary?: string | string[] | undefined;
  link?: string | undefined;
  url?: string | undefined;
  caption: string;
  hashtags: string[];
  _source?: string | undefined;
  image_url?: string | undefined;
  image_asset_id?: string | undefined;
}

export interface SessionView {
  session_id: string;
  last_topic: string | null;
  last_platform: string | null;
  last_content_intent: string | null;
  last_generated_posts: RawPost[];
  last_output: string | null;
  active_constraints: Array<string | { type?: string | undefined; value?: string | undefined }>;
  leftover_fetch_pool?: Array<Record<string, unknown>> | undefined;
  message_history: Array<{
    role: "user" | "assistant" | "tool" | string;
    content: string;
    [key: string]: unknown;
  }>;
  rolling_summary?: string | undefined;
  gate_tokens_used?: number | undefined;
}

export interface ChatRequest {
  message: string;
  session_id?: string | null | undefined;
  platform?: string | null | undefined;
  posts?: number | undefined;
  verbose?: boolean | undefined;
}

export interface ChatResponse {
  status: "done" | "processing" | "error" | string;
  session_id: string;
  action: string;
  reply?: string | null | undefined;
  job_id?: string | null | undefined;
  tokens_used?: number | null | undefined;
}

export interface JobStatusResponse {
  status: "done" | "processing" | "error" | string;
  action?: string | null | undefined;
  reply?: string | null | undefined;
  detail?: string | null | undefined;
}

export interface ApiErrorDetail {
  detail?: string | Array<{ loc: string[]; msg: string; type: string }> | undefined;
  message?: string | undefined;
  retry_after?: number | undefined;
}

// ── Image Subsystem API Contracts ──────────────────────────────────────────

export interface ImageGenerateRequest {
  session_id: string;
  post_number: number;
  post_data: Record<string, any>;
  platform?: string | undefined;
  visual_profile_id?: string | null | undefined;
  custom_prompt?: string | null | undefined;
  reference_asset_id?: string | null | undefined;
  reference_strength?: number | undefined;
  generation_params?: Record<string, any> | undefined;
}

export interface BatchImageGenerateRequest {
  session_id: string;
  posts?: Array<Record<string, any>> | undefined;
  platform?: string | undefined;
  visual_profile_id?: string | null | undefined;
}

export interface ImageJobResponse {
  job_id: string;
  asset_id: string;
  status: "queued" | "generating" | "completed" | "failed" | string;
  message: string;
}

export interface BatchImageJobResponse {
  session_id: string;
  jobs: Array<{
    post_number: number;
    job_id: string;
    asset_id: string;
  }>;
  total_enqueued: number;
}

export interface ImageJobStatusResponse {
  job_id: string;
  status: "queued" | "generating" | "completed" | "failed" | string;
  asset_id?: string | null | undefined;
  image_url?: string | null | undefined;
  error?: string | null | undefined;
  progress_message?: string | undefined;
}

export interface ImageAssetMeta {
  id: string;
  user_id?: number | null | undefined;
  session_id: string;
  post_number: number;
  mode: string;
  prompt: string;
  negative_prompt: string;
  visual_profile_id?: string | null | undefined;
  provider_name: string;
  model_name: string;
  storage_backend: string;
  storage_key: string;
  content_type: string;
  file_size_bytes?: number | null | undefined;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface VisualProfileMeta {
  id: string;
  name: string;
  description: string;
  aspect_ratio: string;
  style_prompt: string;
  negative_prompt: string;
  primary_color: string;
  accent_color: string;
  is_default: boolean;
  watermark_enabled: boolean;
  watermark_text?: string | null | undefined;
  sample_asset_id?: string | null | undefined;
}

export interface VisualProfileResponse {
  profiles: VisualProfileMeta[];
}

export interface VisualProfileCreateRequest {
  name: string;
  description?: string | undefined;
  aspect_ratio?: string | undefined;
  style_prompt: string;
  negative_prompt?: string | undefined;
  primary_color?: string | undefined;
  accent_color?: string | undefined;
  is_default?: boolean | undefined;
  watermark_enabled?: boolean | undefined;
  watermark_text?: string | undefined;
}
