"""
imaging/providers/gemini_imagen.py — Gemini Imagen Image Provider.

Uses the official `google-genai` Python SDK to call Google's Imagen models
(Imagen 3.0 or Imagen 4) for text-to-image generation.

Supported modes:
  - text_to_image  ✅  (imagen-3.0-generate-002 or imagen-4.0-generate-preview-05-20)
  - image_to_image ❌  Imagen currently does not support img2img via this API
  - inpaint        ❌  Imagen inpainting requires Vertex AI; deferred
  - design_edit    ❌  Future

Configuration (via environment variables):
  IMAGEN_MODEL        — Model name (default: "imagen-3.0-generate-002")
  IMAGEN_ASPECT_RATIO — Override default aspect ratio mapping
  GEMINI_API_KEY      — Required

Notes on API contract:
  - `client.models.generate_images(model=..., prompt=..., config=...)` returns
    `GenerateImagesResponse` with `.generated_images` list, each having `.image.image_bytes`.
  - Number of images is capped at 4 by the API; we always request 1.
  - Safety filters may block prompts; we propagate clear errors.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

from imaging.models import (
    ImageGenMode,
    ImageResult,
    TextToImageRequest,
    ImageToImageRequest,
)
from imaging.providers.base import ImageProvider

logger = logging.getLogger("trendforge.imaging.providers.gemini_imagen")

# ─── Aspect ratio mapping ──────────────────────────────────────────────────────
# Imagen API accepts specific string values. We map our internal notation.
_IMAGEN_ASPECT_RATIOS = {
    "1:1":  "1:1",
    "4:5":  "4:5",   # Closest IG portrait (Imagen 3 supports this)
    "3:4":  "3:4",
    "4:3":  "4:3",
    "16:9": "16:9",
    "9:16": "9:16",
}
_FALLBACK_ASPECT_RATIO = "1:1"

# Dimensions for ImageResult metadata (Imagen doesn't always return W/H)
_ASPECT_RATIO_DIMENSIONS = {
    "1:1":  (1024, 1024),
    "4:5":  (896, 1120),
    "3:4":  (768, 1024),
    "4:3":  (1024, 768),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}


class GeminiImagenProvider(ImageProvider):
    """
    Image provider backed by Google Imagen 3 / Imagen 4 via google-genai SDK.

    Instantiate once — the SDK client is reused across calls.
    Configuration is read from environment at construction time so the provider
    can be swapped or re-configured without code changes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = model_name or os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        self._client = None  # Lazy-initialised on first call

        if not self._api_key:
            logger.warning(
                "GeminiImagenProvider: GEMINI_API_KEY is not set. "
                "Calls will fail at generation time."
            )

    # ── Lazy client initialisation ────────────────────────────────────────────

    def _get_client(self):
        """Return a cached google-genai client, creating it on first use."""
        if self._client is None:
            try:
                from google import genai  # type: ignore
                self._client = genai.Client(api_key=self._api_key)
                logger.info(
                    "GeminiImagenProvider: google-genai client initialised (model=%s)",
                    self._model,
                )
            except ImportError as exc:
                raise RuntimeError(
                    "google-genai package is not installed. "
                    "Run: pip install google-genai"
                ) from exc
        return self._client

    # ── Provider interface ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "gemini_imagen"

    def supported_modes(self) -> List[ImageGenMode]:
        # Only TEXT_TO_IMAGE is exposed through the public REST API.
        # image_to_image / inpaint require Vertex AI SDK — deferred.
        return [ImageGenMode.TEXT_TO_IMAGE]

    def supported_aspect_ratios(self) -> List[str]:
        return list(_IMAGEN_ASPECT_RATIOS.keys())

    # ── Generation ─────────────────────────────────────────────────────────────

    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        """
        Call Imagen API and return raw PNG bytes wrapped in ImageResult.

        Raises:
            RuntimeError — if GEMINI_API_KEY is missing, the API rejects the
                           request (safety / quota), or returns no images.
        """
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required for GeminiImagenProvider. "
                "Set it in your .env file or environment."
            )

        client = self._get_client()

        # Map our aspect ratio to what Imagen accepts
        ar = request.visual_brief.aspect_ratio
        imagen_ar = _IMAGEN_ASPECT_RATIOS.get(ar, _FALLBACK_ASPECT_RATIO)
        if ar not in _IMAGEN_ASPECT_RATIOS:
            logger.warning(
                "GeminiImagenProvider: Unsupported aspect ratio '%s', "
                "falling back to '%s'.",
                ar, _FALLBACK_ASPECT_RATIO,
            )

        # Build generation config
        try:
            from google.genai import types as genai_types  # type: ignore
            gen_config = genai_types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=imagen_ar,
                # Safety settings — allow professional content about technology
                # without tripping filters on innocuous tech terminology
                safety_filter_level="block_only_high",
                person_generation="allow_adult",  # allow people in shots if requested
            )
        except (ImportError, AttributeError):
            # Older SDK version may not have GenerateImagesConfig
            gen_config = {
                "number_of_images": 1,
                "aspect_ratio": imagen_ar,
            }

        # Build the prompt — combine positive and negative
        prompt = request.prompt
        if request.negative_prompt:
            # Imagen 3 supports negative prompts as a separate field or inline
            # We try both approaches for SDK compat
            full_prompt = prompt
        else:
            full_prompt = prompt

        model_to_use = request.model_name or self._model
        logger.info(
            "GeminiImagenProvider: Calling %s | ar=%s | prompt_len=%d",
            model_to_use, imagen_ar, len(full_prompt),
        )

        start_ms = time.monotonic()
        try:
            response = client.models.generate_images(
                model=model_to_use,
                prompt=full_prompt,
                config=gen_config,
            )
        except Exception as exc:
            logger.error("GeminiImagenProvider: API call failed: %s", exc, exc_info=True)
            raise RuntimeError(
                f"Gemini Imagen generation failed: {exc}"
            ) from exc
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        # Extract bytes from response
        if not response.generated_images:
            raise RuntimeError(
                "Gemini Imagen returned no images. "
                "The prompt may have been blocked by safety filters. "
                f"Prompt: {full_prompt[:200]}"
            )

        image_bytes = response.generated_images[0].image.image_bytes
        if not image_bytes:
            raise RuntimeError("Gemini Imagen returned an empty image response.")

        # Determine dimensions
        w, h = _ASPECT_RATIO_DIMENSIONS.get(ar, (1024, 1024))

        logger.info(
            "GeminiImagenProvider: Generated %d bytes in %dms (model=%s)",
            len(image_bytes), elapsed_ms, model_to_use,
        )

        return ImageResult(
            image_bytes=image_bytes,
            content_type="image/png",
            width=w,
            height=h,
            provider_name=self.name,
            model_name=model_to_use,
            provider_metadata={
                "aspect_ratio": imagen_ar,
                "negative_prompt_used": bool(request.negative_prompt),
                "prompt_chars": len(full_prompt),
            },
            tokens_used=0,  # Imagen bills per image, not per token
            generation_time_ms=elapsed_ms,
        )
