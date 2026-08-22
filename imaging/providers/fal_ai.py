"""
imaging/providers/fal_ai.py — fal.ai Provider for Recraft V3 & FLUX.1.

fal.ai provides ultra-fast inference for:
  - Recraft V3 (rated #1 for vector art, design graphics, and style reference)
  - FLUX.1 [schnell] & FLUX.1 [dev]
  - FLUX.1 [redux] / Style Variation

Configuration:
  FAL_KEY   — fal.ai API key (format: "key_id:key_secret")
  FAL_MODEL — Default model (default: "fal-ai/recraft-v3")
"""

from __future__ import annotations

import logging
import os
import time
import urllib.request
import json
from typing import List, Optional

from imaging.models import (
    ImageGenMode,
    ImageResult,
    TextToImageRequest,
    ImageToImageRequest,
)
from imaging.providers.base import ImageProvider

logger = logging.getLogger("trendforge.imaging.providers.fal_ai")

FAL_MODELS = [
    "fal-ai/recraft-v3",       # Default: #1 for graphic design & style reference
    "fal-ai/flux/schnell",     # Ultra-fast 4-step Flux
    "fal-ai/flux/dev",         # High-detail 28-step Flux
    "fal-ai/flux-redux",       # Style transfer / reference image variation
]

# Aspect ratio map for fal.ai
_FAL_ASPECT_RATIOS = {
    "1:1": "square_hd",
    "4:5": "portrait_4_5",
    "3:4": "portrait_4_3",
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "4:3": "landscape_4_3",
}


class FalAIProvider(ImageProvider):
    """
    fal.ai Provider supporting Recraft V3, FLUX, and Style Reference.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 120,
        **kwargs,
    ) -> None:
        self._api_key = api_key or os.getenv("FAL_KEY", "")
        self._model = model_name or os.getenv("FAL_MODEL", "fal-ai/recraft-v3")
        self._timeout = timeout

        if not self._api_key:
            logger.warning(
                "FalAIProvider: FAL_KEY is not set. Live generation calls will fail "
                "or fall back to Pollinations."
            )
        else:
            logger.info("FalAIProvider: initialised with model=%s", self._model)

    @property
    def name(self) -> str:
        return "fal_ai"

    def supported_modes(self) -> List[ImageGenMode]:
        return [ImageGenMode.TEXT_TO_IMAGE, ImageGenMode.IMAGE_TO_IMAGE]

    def supported_aspect_ratios(self) -> List[str]:
        return list(_FAL_ASPECT_RATIOS.keys())

    def _call_fal_rest_api(self, endpoint: str, payload: dict) -> bytes:
        """Call fal.ai synchronous or queue REST API."""
        if not self._api_key:
            raise RuntimeError(
                "FAL_KEY is not configured. Add FAL_KEY=... to your .env file "
                "or switch to IMAGE_PROVIDER=pollinations (100% free)."
            )

        url = f"https://fal.run/{endpoint}"
        headers = {
            "Authorization": f"Key {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"fal.ai API error ({e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"fal.ai request failed: {e}") from e

        # Extract image URL from response
        images = resp_json.get("images") or []
        if not images:
            raise RuntimeError(f"fal.ai returned no images in response: {resp_json}")

        img_url = images[0].get("url")
        if not img_url:
            raise RuntimeError(f"No image URL in fal.ai result: {images[0]}")

        # Download image bytes
        with urllib.request.urlopen(img_url, timeout=30) as img_resp:
            return img_resp.read()

    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        t0 = time.time()
        aspect_ratio_str = "4:5"
        if request.visual_brief and request.visual_brief.aspect_ratio:
            aspect_ratio_str = request.visual_brief.aspect_ratio

        image_size = _FAL_ASPECT_RATIOS.get(aspect_ratio_str, "portrait_4_5")

        payload = {
            "prompt": request.prompt,
            "image_size": image_size,
        }

        # Model-specific payloads
        if "recraft" in self._model:
            payload["style"] = "digital_illustration"
            payload["substyle"] = "tech"

        image_bytes = self._call_fal_rest_api(self._model, payload)
        duration_ms = int((time.time() - t0) * 1000)

        return ImageResult(
            image_bytes=image_bytes,
            content_type="image/png",
            provider_name="fal_ai",
            provider_metadata={
                "model": self._model,
                "duration_ms": duration_ms,
                "aspect_ratio": aspect_ratio_str,
            },
        )

    def generate_image_to_image(self, request: ImageToImageRequest) -> ImageResult:
        """Style transfer / reference image generation."""
        t0 = time.time()
        payload = {
            "prompt": request.prompt,
        }
        if request.reference_image_bytes:
            import base64
            b64 = base64.b64encode(request.reference_image_bytes).decode("utf-8")
            payload["image_url"] = f"data:image/png;base64,{b64}"

        endpoint = "fal-ai/recraft-v3" if "recraft" in self._model else "fal-ai/flux-redux"
        image_bytes = self._call_fal_rest_api(endpoint, payload)
        duration_ms = int((time.time() - t0) * 1000)

        return ImageResult(
            image_bytes=image_bytes,
            content_type="image/png",
            provider_name="fal_ai",
            provider_metadata={
                "model": endpoint,
                "duration_ms": duration_ms,
                "mode": "image_to_image",
            },
        )
