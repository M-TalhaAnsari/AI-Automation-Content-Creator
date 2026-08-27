"""
api/web/routes/preferences_routes.py -- User Memory, Brand Persona & Studio Settings Endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.web.dependencies.auth_deps import verify_jwt
from api.web import db
from api.web.services.cache_service import FAST_MEMORY_CACHE

router = APIRouter(prefix="/preferences", tags=["Preferences & Memory"])


class PreferencesPayload(BaseModel):
    brand_name: Optional[str] = ""
    brand_handle: Optional[str] = "@aiflick"
    target_audience: Optional[str] = ""
    tone_of_voice: Optional[str] = "punchy, authoritative, high-conversion"
    custom_rules: Optional[str] = ""
    show_watermark: Optional[bool] = True
    preferred_model_tier: Optional[str] = "free"


@router.get("")
def get_preferences(client_name: str = Depends(verify_jwt)):
    """Retrieve creator brand memory, tone, audience and studio settings."""
    user_id = int(client_name.split(":", 1)[1])
    cache_key = f"user_prefs:{user_id}"
    cached = FAST_MEMORY_CACHE.get(cache_key)
    if cached:
        return cached

    prefs = db.get_user_preferences(user_id)
    FAST_MEMORY_CACHE.set(cache_key, prefs, ttl_sec=120)
    return prefs


@router.post("")
def save_preferences(body: PreferencesPayload, client_name: str = Depends(verify_jwt)):
    """Save long-term creator memory, tone, and studio defaults."""
    user_id = int(client_name.split(":", 1)[1])
    updated = db.save_user_preferences(user_id, body.model_dump())
    cache_key = f"user_prefs:{user_id}"
    FAST_MEMORY_CACHE.set(cache_key, updated, ttl_sec=120)
    return {"ok": True, "preferences": updated}
