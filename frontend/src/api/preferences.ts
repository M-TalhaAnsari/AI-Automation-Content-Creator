/**
 * frontend/src/api/preferences.ts -- User Memory, Brand Preferences & Model Tiers API Client
 */
import { apiFetch } from "./client";

export interface UserPreferences {
  brand_name: string;
  brand_handle: string;
  target_audience: string;
  tone_of_voice: string;
  custom_rules: string;
  show_watermark: boolean;
  preferred_model_tier: string;
}

export interface PlanInfo {
  id: string;
  name: string;
  price_usd: number;
  description: string;
  text_model: string;
  image_model: string;
  image_provider: string;
  daily_post_limit: number;
  unlimited: boolean;
  carousel_slides_max: number;
  watermark: boolean;
  custom_branding: boolean;
  priority: boolean;
}

export async function getPreferences(): Promise<UserPreferences> {
  return apiFetch<UserPreferences>("/preferences", { method: "GET" });
}

export async function savePreferences(prefs: Partial<UserPreferences>): Promise<{ ok: boolean; preferences: UserPreferences }> {
  return apiFetch<{ ok: boolean; preferences: UserPreferences }>("/preferences", {
    method: "POST",
    body: JSON.stringify(prefs),
  });
}

export async function getTierPlans(): Promise<{ plans: PlanInfo[] }> {
  return apiFetch<{ plans: PlanInfo[] }>("/auth/plans", { method: "GET" });
}

export async function upgradeTier(tier: string): Promise<{ ok: boolean; tier: string; plan_name: string }> {
  return apiFetch<{ ok: boolean; tier: string; plan_name: string }>("/auth/upgrade", {
    method: "POST",
    body: JSON.stringify({ tier }),
  });
}
