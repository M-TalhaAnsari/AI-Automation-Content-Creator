/**
 * API Data Contracts matching FastAPI Backend Pydantic Models
 */

export interface SignupRequest {
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
  email: string;
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
