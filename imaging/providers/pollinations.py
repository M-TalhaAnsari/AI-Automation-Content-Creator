"""
imaging/providers/pollinations.py — Pollinations.ai Image Provider.

Pollinations.ai provides 100% FREE image generation with no API key required.
It uses open-source models (Flux, Stable Diffusion, SDXL, etc.) via a public REST API.

API Endpoint:
  GET  https://image.pollinations.ai/prompt/{encoded_prompt}
       ?model=flux            — Model name (flux, flux-pro, sdxl, turbo, etc.)
       &width=1024            — Output width
       &height=1024           — Output height
       &seed=42               — Optional seed for reproducibility
       &nologo=true           — Remove Pollinations watermark
       &enhance=false         — Disable auto prompt enhancement (we handle prompts ourselves)
       &nofeed=true           — Don't publish to public feed (privacy)

Available free models (as of 2026):
  - flux           → FLUX.1-schnell (fast, good quality)
  - flux-pro       → FLUX.1-pro (higher quality, same speed class)
  - flux-realism   → FLUX.1 with realism LoRA
  - turbo          → SDXL-Turbo (very fast, lower quality)
  - dreamshaper    → DreamShaper XL

No authentication. Rate limits are generous for development use.
For production, consider a small delay between requests.

Supported modes:
  - text_to_image ✅
  - image_to_image ❌  (Pollinations does not offer img2img endpoint)

Supported aspect ratios → pixel dimensions:
  1:1   → 1024×1024
  4:5   → 896×1120    (Instagram portrait)
  3:4   → 768×1024
  9:16  → 720×1280    (Reels/Stories/Shorts)
  16:9  → 1280×720    (YouTube)
  4:3   → 1024×768

Configuration (via environment variables):
  POLLINATIONS_MODEL    — Default model (default: "flux")
  POLLINATIONS_TIMEOUT  — HTTP timeout in seconds (default: 90)
  POLLINATIONS_SEED     — Optional fixed seed (default: None = random)
"""

from __future__ import annotations

import logging
import os
import time
import urllib.parse
from typing import List, Optional

from imaging.models import (
    ImageGenMode,
    ImageResult,
    TextToImageRequest,
)
from imaging.providers.base import ImageProvider

logger = logging.getLogger("trendforge.imaging.providers.pollinations")

# ── Constants ──────────────────────────────────────────────────────────────────

_BASE_URL = "https://image.pollinations.ai/prompt"

_ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1":  (1024, 1024),
    "4:5":  (896, 1120),
    "3:4":  (768, 1024),
    "4:3":  (1024, 768),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}

# Available models on Pollinations free API
POLLINATIONS_MODELS = [
    "flux",           # Default — fast, high quality
    "flux-pro",       # Higher quality
    "flux-realism",   # Realism LoRA
    "turbo",          # SDXL-Turbo — fastest
    "dreamshaper",    # DreamShaper XL — artistic
    "any-dark",       # Dark, cinematic aesthetic
]


class PollinationsProvider(ImageProvider):
    """
    100% free image generation via Pollinations.ai.

    No API key required. Uses FLUX or SDXL models under the hood.
    Images are downloaded as JPEG bytes and returned directly.

    Usage:
        provider = PollinationsProvider()
        # or with explicit model:
        provider = PollinationsProvider(model_name="flux-pro")
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        seed: Optional[int] = None,
        **kwargs,
    ) -> None:
        self._default_model = model_name or os.getenv("POLLINATIONS_MODEL", "flux")
        self._timeout = timeout or int(os.getenv("POLLINATIONS_TIMEOUT", "90"))
        _seed_env = os.getenv("POLLINATIONS_SEED", "")
        self._seed = seed or (int(_seed_env) if _seed_env.isdigit() else None)

        logger.info(
            "PollinationsProvider: initialised (model=%s, timeout=%ds)",
            self._default_model, self._timeout,
        )

    # ── Provider interface ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "pollinations"

    def supported_modes(self) -> List[ImageGenMode]:
        return [ImageGenMode.TEXT_TO_IMAGE]

    def supported_aspect_ratios(self) -> List[str]:
        return list(_ASPECT_DIMENSIONS.keys())

    # ── Generation ─────────────────────────────────────────────────────────────

    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        """
        Call Pollinations free API and return image bytes as ImageResult.

        The prompt is URL-encoded and passed as a path segment.
        Negative prompts are appended inline using standard diffusion notation.
        """
        try:
            import urllib.request
        except ImportError:
            pass  # stdlib — always available

        # Determine model
        model = request.model_name or self._default_model

        # Determine dimensions
        ar = request.visual_brief.aspect_ratio
        width, height = _ASPECT_DIMENSIONS.get(ar, (1024, 1024))

        # Build combined prompt (Pollinations supports inline negative)
        prompt = request.prompt
        if request.negative_prompt:
            prompt = f"{prompt} | negative: {request.negative_prompt}"

        # Encode prompt as URL path segment
        encoded_prompt = urllib.parse.quote(prompt, safe="")

        # Build query string
        params = {
            "model":   model,
            "width":   str(width),
            "height":  str(height),
            "nologo":  "true",
            "enhance": "false",   # We build rich prompts ourselves
            "nofeed":  "true",    # Don't publish to Pollinations public feed
        }
        if self._seed is not None:
            params["seed"] = str(self._seed)

        query = urllib.parse.urlencode(params)
        url = f"{_BASE_URL}/{encoded_prompt}?{query}"

        logger.info(
            "PollinationsProvider: Requesting image | model=%s | size=%dx%d | prompt_len=%d",
            model, width, height, len(request.prompt),
        )

        start_ms = time.monotonic()
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "TrendForge-ImageGen/1.0",
                    "Accept": "image/jpeg, image/png, image/*",
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                image_bytes = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
        except Exception as exc:
            logger.error(
                "PollinationsProvider: Request failed for model=%s: %s",
                model, exc, exc_info=True,
            )
            raise RuntimeError(
                f"Pollinations image generation failed: {exc}. "
                f"Model: {model}, Prompt length: {len(prompt)}"
            ) from exc

        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        if not image_bytes or len(image_bytes) < 1000:
            raise RuntimeError(
                f"Pollinations returned suspiciously small response ({len(image_bytes)} bytes). "
                "The prompt may have been filtered or the service may be temporarily down."
            )

        # Normalise content type
        if "png" in content_type:
            final_content_type = "image/png"
        elif "webp" in content_type:
            final_content_type = "image/webp"
        else:
            final_content_type = "image/jpeg"

        logger.info(
            "PollinationsProvider: Received %d bytes in %dms (%s)",
            len(image_bytes), elapsed_ms, final_content_type,
        )

        return ImageResult(
            image_bytes=image_bytes,
            content_type=final_content_type,
            width=width,
            height=height,
            provider_name=self.name,
            model_name=model,
            provider_metadata={
                "api_url": url[:200],  # Truncate for storage — avoid storing full prompt in metadata
                "aspect_ratio": ar,
                "seed": self._seed,
                "nologo": True,
                "nofeed": True,
            },
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )
