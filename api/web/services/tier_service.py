"""
api/web/services/tier_service.py -- Tier management, model quotas, and monetization rules.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TierConfig:
    id: str
    name: str
    price_monthly_usd: float
    description: str
    text_model: str
    image_model: str
    image_provider: str
    daily_post_limit: int
    unlimited_posts: bool
    carousel_slides_max: int
    watermark_enabled: bool
    custom_branding: bool
    priority_queue: bool


TIER_PLANS: Dict[str, TierConfig] = {
    "free": TierConfig(
        id="free",
        name="Free Explorer",
        price_monthly_usd=0.0,
        description="100% free tier for creators testing AIFlick with open models.",
        text_model="gemini-2.0-flash",
        image_model="flux",
        image_provider="pollinations",
        daily_post_limit=15,
        unlimited_posts=False,
        carousel_slides_max=5,
        watermark_enabled=True,
        custom_branding=False,
        priority_queue=False,
    ),
    "creator": TierConfig(
        id="creator",
        name="Creator Pro",
        price_monthly_usd=9.0,
        description="For growing influencers & solo creators requiring clean watermark-free visuals.",
        text_model="gemini-2.5-flash",
        image_model="flux-pro",
        image_provider="pollinations",
        daily_post_limit=75,
        unlimited_posts=False,
        carousel_slides_max=10,
        watermark_enabled=False,
        custom_branding=True,
        priority_queue=True,
    ),
    "agency": TierConfig(
        id="agency",
        name="Agency & Studio",
        price_monthly_usd=29.0,
        description="Unlimited generations with high-end reasoning and studio-grade Imagen 3 / FLUX.1.",
        text_model="gemini-2.5-pro",
        image_model="imagen-3.0-generate-002",
        image_provider="gemini_imagen",
        daily_post_limit=999999,
        unlimited_posts=True,
        carousel_slides_max=15,
        watermark_enabled=False,
        custom_branding=True,
        priority_queue=True,
    ),
}


def get_tier_config(tier_id: Optional[str] = "free") -> TierConfig:
    normalized = (tier_id or "free").lower().strip()
    return TIER_PLANS.get(normalized, TIER_PLANS["free"])


def list_available_plans() -> list[Dict[str, Any]]:
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "price_usd": plan.price_monthly_usd,
            "description": plan.description,
            "text_model": plan.text_model,
            "image_model": plan.image_model,
            "image_provider": plan.image_provider,
            "daily_post_limit": plan.daily_post_limit,
            "unlimited": plan.unlimited_posts,
            "carousel_slides_max": plan.carousel_slides_max,
            "watermark": plan.watermark_enabled,
            "custom_branding": plan.custom_branding,
            "priority": plan.priority_queue,
        }
        for plan in TIER_PLANS.values()
    ]
