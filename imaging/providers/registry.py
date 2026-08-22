"""
imaging/providers/registry.py — Pluggable Image Provider Registry.

Allows registering, discovering, and instantiating image providers at runtime.
New providers can be added without modifying the core orchestrator or API routes.

Built-in providers:
  - mock           → MockImageProvider    (synthetic PNGs, no external calls)
  - gemini_imagen  → GeminiImagenProvider (Google Imagen 3 / Imagen 4 via google-genai)
  - pollinations   → PollinationsProvider (FREE — Flux/SDXL via Pollinations.ai, no key needed)
  - huggingface    → HuggingFaceProvider  (FREE — any HF Inference API model, optional token)

To add a new provider:
  1. Create imaging/providers/my_provider.py implementing ImageProvider.
  2. Import it here and add to _PROVIDER_REGISTRY.
  3. Set IMAGE_PROVIDER=my_provider in .env.
  — Nothing else needs to change.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from imaging.providers.base import ImageProvider
from imaging.providers.mock import MockImageProvider

logger = logging.getLogger("trendforge.imaging.providers")

# ── Registry ───────────────────────────────────────────────────────────────────
# All providers are lazily imported to avoid mandatory dependency installation.
# E.g. google-genai is only needed if you use gemini_imagen.

_PROVIDER_REGISTRY: Dict[str, Type[ImageProvider]] = {
    "mock": MockImageProvider,
}

# Singleton instances — created on first get_provider() call
_PROVIDER_INSTANCES: Dict[str, ImageProvider] = {}


def _bootstrap_providers() -> None:
    """
    Register all built-in providers.

    Uses conditional imports so that missing optional dependencies
    (e.g. google-genai) cause a clear error only when that provider is used,
    not at import time.
    """
    # ── Gemini Imagen ──────────────────────────────────────────────────────────
    try:
        from imaging.providers.gemini_imagen import GeminiImagenProvider
        _PROVIDER_REGISTRY["gemini_imagen"] = GeminiImagenProvider
        logger.debug("Registered provider: gemini_imagen")
    except ImportError as exc:
        logger.warning("gemini_imagen provider unavailable: %s", exc)

    # ── Pollinations (FREE, no API key) ────────────────────────────────────────
    try:
        from imaging.providers.pollinations import PollinationsProvider
        _PROVIDER_REGISTRY["pollinations"] = PollinationsProvider
        logger.debug("Registered provider: pollinations")
    except ImportError as exc:
        logger.warning("pollinations provider unavailable: %s", exc)

    # ── Hugging Face Inference API (FREE with optional token) ──────────────────
    try:
        from imaging.providers.huggingface import HuggingFaceProvider
        _PROVIDER_REGISTRY["huggingface"] = HuggingFaceProvider
        logger.debug("Registered provider: huggingface")
    except ImportError as exc:
        logger.warning("huggingface provider unavailable: %s", exc)

    # ── fal.ai (Recraft V3 & FLUX.1) ──────────────────────────────────────────
    try:
        from imaging.providers.fal_ai import FalAIProvider
        _PROVIDER_REGISTRY["fal_ai"] = FalAIProvider
        logger.debug("Registered provider: fal_ai")
    except ImportError as exc:
        logger.warning("fal_ai provider unavailable: %s", exc)


# Run bootstrap at module load time (safe — only does class registration, no I/O)
_bootstrap_providers()


# ── Public API ─────────────────────────────────────────────────────────────────

def register_provider(name: str, provider_cls: Type[ImageProvider]) -> None:
    """Register a new image provider class under a given name."""
    _PROVIDER_REGISTRY[name.lower()] = provider_cls
    # Bust the singleton cache if a new class replaces an existing one
    _PROVIDER_INSTANCES.pop(name.lower(), None)
    logger.info("Registered image provider: %s (%s)", name, provider_cls.__name__)


def get_provider(name: str = "mock", **kwargs) -> ImageProvider:
    """
    Get or instantiate an ImageProvider by name.

    Caches provider instances as singletons (one per provider name).
    Extra keyword arguments are forwarded to the provider constructor on
    first instantiation (e.g. api_key, model_name, timeout).

    Falls back to 'mock' if the requested provider is not registered.
    """
    normalized = name.lower().strip()

    if normalized not in _PROVIDER_REGISTRY:
        available = list(_PROVIDER_REGISTRY.keys())
        logger.warning(
            "Image provider '%s' is not registered. "
            "Available providers: %s. Falling back to 'mock'.",
            name, available,
        )
        normalized = "mock"

    if normalized not in _PROVIDER_INSTANCES:
        provider_cls = _PROVIDER_REGISTRY[normalized]
        try:
            _PROVIDER_INSTANCES[normalized] = provider_cls(**kwargs)
            logger.info(
                "Instantiated image provider: %s (%s)",
                normalized, provider_cls.__name__,
            )
        except Exception as exc:
            logger.error(
                "Failed to instantiate provider '%s': %s. Using 'mock' as fallback.",
                normalized, exc, exc_info=True,
            )
            _PROVIDER_INSTANCES[normalized] = MockImageProvider()

    return _PROVIDER_INSTANCES[normalized]


def get_provider_fresh(name: str, **kwargs) -> ImageProvider:
    """
    Create a NEW provider instance (bypasses singleton cache).

    Useful in tests or when configuration changes between calls.
    """
    normalized = name.lower().strip()
    if normalized not in _PROVIDER_REGISTRY:
        logger.warning(
            "Provider '%s' not registered. Available: %s.",
            name, list(_PROVIDER_REGISTRY.keys()),
        )
        normalized = "mock"
    provider_cls = _PROVIDER_REGISTRY[normalized]
    return provider_cls(**kwargs)


def list_available_providers() -> list[str]:
    """Return all registered provider names."""
    return list(_PROVIDER_REGISTRY.keys())


def unregister_provider(name: str) -> None:
    """Remove a provider from the registry (useful in tests)."""
    normalized = name.lower()
    _PROVIDER_REGISTRY.pop(normalized, None)
    _PROVIDER_INSTANCES.pop(normalized, None)
