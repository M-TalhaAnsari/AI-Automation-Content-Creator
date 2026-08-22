"""
api/web/image_deps.py — FastAPI Dependency Injection for the Image Subsystem.

Providers are selected at runtime via CONFIG.imaging.provider so you can
switch between mock / pollinations / huggingface / gemini_imagen by changing
IMAGE_PROVIDER in your .env file.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import Depends, Request
from redis import Redis
from rq import Queue

from api.web.auth import verify_identity, verify_jwt
from Config.config import CONFIG
from imaging.providers.registry import get_provider
from imaging.service import ImageService
from memory.redis_session_store import REDIS_URL

logger = logging.getLogger("trendforge.api.image_deps")

_IMAGE_SERVICE_INSTANCE: Optional[ImageService] = None
_REDIS_CONN: Optional[Redis] = None
_IMAGE_QUEUE: Optional[Queue] = None

IMAGE_QUEUE_NAME = getattr(getattr(CONFIG, "imaging", None), "image_queue_name", "trendforge-images")



def get_image_redis_conn() -> Redis:
    """Return persistent Redis connection."""
    global _REDIS_CONN
    if _REDIS_CONN is None:
        _REDIS_CONN = Redis.from_url(REDIS_URL)
    return _REDIS_CONN


def get_image_queue(conn: Redis = Depends(get_image_redis_conn)) -> Queue:
    """Return RQ Queue for the dedicated trendforge-images queue."""
    global _IMAGE_QUEUE
    if _IMAGE_QUEUE is None:
        queue_name = CONFIG.imaging.image_queue_name
        _IMAGE_QUEUE = Queue(queue_name, connection=conn)
    return _IMAGE_QUEUE


def _build_provider_kwargs(provider_name: str) -> dict:
    """
    Build provider constructor kwargs specifically tailored for the selected provider.
    Prevents passing Gemini model names to Pollinations or HuggingFace.
    """
    img = CONFIG.imaging
    if provider_name == "gemini_imagen":
        return {
            "api_key": CONFIG.models.gemini_api_key or None,
            "model_name": img.imagen_model or "imagen-3.0-generate-002",
        }
    elif provider_name == "pollinations":
        return {
            "model_name": img.pollinations_model or "flux",
            "timeout": img.pollinations_timeout,
            "seed": img.pollinations_seed,
        }
    elif provider_name == "huggingface":
        return {
            "api_token": img.hf_token or None,
            "model_name": img.hf_model or "black-forest-labs/FLUX.1-schnell",
            "timeout": img.hf_timeout,
        }
    elif provider_name == "fal_ai":
        return {
            "api_key": img.fal_key or None,
            "model_name": img.fal_model or "fal-ai/recraft-v3",
        }
    return {}


def get_image_service() -> ImageService:
    """
    Provide ImageService singleton.

    Provider is resolved from CONFIG.imaging.provider on first call.
    To change provider: set IMAGE_PROVIDER=pollinations|huggingface|gemini_imagen|mock in .env
    and restart the app — no code change needed.
    """
    global _IMAGE_SERVICE_INSTANCE
    if _IMAGE_SERVICE_INSTANCE is None:
        provider_name = CONFIG.imaging.provider
        logger.info("Initialising ImageService with provider: %s", provider_name)

        # Build provider with provider-specific constructor args
        provider = get_provider(provider_name, **_build_provider_kwargs(provider_name))

        _IMAGE_SERVICE_INSTANCE = ImageService(provider=provider)
        logger.info(
            "ImageService ready (provider=%s, storage=%s)",
            provider.name, CONFIG.imaging.storage_backend,
        )
    return _IMAGE_SERVICE_INSTANCE


def reset_image_service() -> None:
    """
    Force re-creation of the ImageService singleton on next call.
    Useful in tests and when switching providers at runtime.
    """
    global _IMAGE_SERVICE_INSTANCE, _IMAGE_QUEUE, _REDIS_CONN
    _IMAGE_SERVICE_INSTANCE = None
    _IMAGE_QUEUE = None
    _REDIS_CONN = None


def extract_user_id(client_name: str) -> Optional[int]:
    """Parse user ID from client identity ('user:123' -> 123, 'anon:xyz' -> None)."""
    if client_name.startswith("user:"):
        try:
            return int(client_name.split(":", 1)[1])
        except (ValueError, IndexError):
            return None
    return None
