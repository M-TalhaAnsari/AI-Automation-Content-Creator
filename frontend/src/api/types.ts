/**
 * frontend/src/api/types.ts — API Data Contracts matching FastAPI Backend Pydantic Models
 */

export interface SignupRequest {
  name?: string;
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
  name?: string;
  email: string;
  tier?: string;
}

export interface SessionListItem {
  session_id: string;
  title: string | null;
  created_at: string;
  last_active_at: string;
}

export interface RawPost {
  number?: number;
  title: string;
  hook: string;
  summary?: string | string[];
  link?: string;
  url?: string;
  caption: string;
  hashtags: string[];
  _source?: string;
  image_url?: string;
  image_asset_id?: string;
}

export interface SessionView {
  session_id: string;
  last_topic: string | null;
  last_platform: string | null;
  last_content_intent: string | null;
  last_generated_posts: RawPost[];
  last_output: string | null;
  active_constraints: Array<string | { type?: string; value?: string }>;
  leftover_fetch_pool?: Array<Record<string, unknown>>;
  message_history: Array<{
    role: "user" | "assistant" | "tool" | string;
    content: string;
    [key: string]: unknown;
  }>;
  rolling_summary?: string;
  gate_tokens_used?: number;
}

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  platform?: string | null;
  posts?: number;
  verbose?: boolean;
}

export interface ChatResponse {
  status: "done" | "processing" | "error" | string;
  session_id: string;
  action: string;
  reply?: string | null;
  job_id?: string | null;
  tokens_used?: number | null;
}

export interface JobStatusResponse {
  status: "done" | "processing" | "error" | string;
  action?: string | null;
  reply?: string | null;
  detail?: string | null;
}

export interface ApiErrorDetail {
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
  message?: string;
  retry_after?: number;
}

// ── Image Subsystem API Contracts ──────────────────────────────────────────

export interface ImageGenerateRequest {
  session_id: string;
  post_number: number;
  post_data: Record<string, any>;
  platform?: string;
  visual_profile_id?: string | null;
  custom_prompt?: string | null;
  reference_asset_id?: string | null;
  reference_strength?: number;
  generation_params?: Record<string, any>;
}

export interface BatchImageGenerateRequest {
  session_id: string;
  posts?: Array<Record<string, any>>;
  platform?: string;
  visual_profile_id?: string | null;
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
  asset_id?: string | null;
  image_url?: string | null;
  error?: string | null;
  progress_message?: string;
}

export interface ImageAssetMeta {
  id: string;
  user_id?: number | null;
  session_id: string;
  post_number: number;
  mode: string;
  prompt: string;
  negative_prompt: string;
  visual_profile_id?: string | null;
  provider_name: string;
  model_name: string;
  storage_backend: string;
  storage_key: string;
  content_type: string;
  file_size_bytes?: number | null;
  status: string;
  created_at: string;
  updated_at: string;
  url: string;
}

export interface ColorPalette {
  primary: string;
  secondary: string;
  accent: string;
  text: string;
  surface: string;
}

export interface VisualProfileResponse {
  id: string;
  name: string;
  description: string;
  color_palette: ColorPalette;
  typography_style: string;
  visual_mood: string;
  default_layout: string;
  is_default: boolean;
}

export interface VisualProfileCreateRequest {
  name: string;
  description?: string;
  color_palette?: Partial<ColorPalette>;
  typography_style?: string;
  visual_mood?: string;
  default_layout?: string;
  is_default?: boolean;
}
