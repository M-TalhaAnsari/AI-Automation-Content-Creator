"""
imaging/providers/huggingface.py — Hugging Face Inference API Image Provider.

Uses the Hugging Face Inference API (free tier with HF_TOKEN) to run
text-to-image models hosted on the HF Hub.

Free tier limits:
  - Unlimited requests on free models (community-hosted)
  - ~100–1000 req/day on accelerated inference endpoints (with token)
  - No GPU allocation needed — HF handles it

Popular supported models (configurable, not hardcoded):
  - black-forest-labs/FLUX.1-schnell   → Best quality, fast (recommended)
  - black-forest-labs/FLUX.1-dev       → Research license, high quality
  - stabilityai/stable-diffusion-xl-base-1.0  → Classic SDXL
  - runwayml/stable-diffusion-v1-5     → Lighter, fast
  - prompthero/openjourney             → Midjourney-like style
  - Lykon/dreamshaper-8                → DreamShaper aesthetic

API Docs: https://huggingface.co/docs/api-inference/tasks/text-to-image

Configuration (via environment variables):
  HF_TOKEN           — Hugging Face API token (free account at huggingface.co)
                       Without token: rate-limited to ~1 req/hr per model
                       With token: 100-1000 req/day free tier
  HF_MODEL           — Default model (default: "black-forest-labs/FLUX.1-schnell")
  HF_TIMEOUT         — HTTP timeout in seconds (default: 120)

Request body:
  {
    "inputs": "<prompt>",
    "parameters": {
        "width": 1024,
        "height": 1024,
        "negative_prompt": "...",
        "num_inference_steps": 20,
        "guidance_scale": 7.5
    }
  }

Response: Raw image bytes (JPEG or PNG) directly from the API.

Supported modes:
  - text_to_image ✅
  - image_to_image ❌  (requires separate img2img endpoint; deferred)

Notes:
  - Some models are "gated" and require accepting their license on HF Hub.
  - If a model is loading (cold start), HF returns 503 with estimated_time.
    We retry once with a backoff.
  - Models return image bytes directly (not JSON) — handled correctly here.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from imaging.models import (
    ImageGenMode,
    ImageResult,
    TextToImageRequest,
)
from imaging.providers.base import ImageProvider

logger = logging.getLogger("trendforge.imaging.providers.huggingface")

# ── Constants ──────────────────────────────────────────────────────────────────

_HF_INFERENCE_BASE = "https://api-inference.huggingface.co/models"

_ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "1:1":  (1024, 1024),
    "4:5":  (896, 1120),
    "3:4":  (768, 1024),
    "4:3":  (1024, 768),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}

# Curated free/open models — user can override via HF_MODEL env var
HUGGINGFACE_FREE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",     # Best quality free model (recommended)
    "black-forest-labs/FLUX.1-dev",         # Research license — high quality
    "stabilityai/stable-diffusion-xl-base-1.0",  # SDXL — classic
    "runwayml/stable-diffusion-v1-5",       # Lightweight, fast
    "prompthero/openjourney",               # Midjourney-like style
    "Lykon/dreamshaper-8",                  # DreamShaper — artistic
    "Linaqruf/animagine-xl-3.0",            # Anime/illustration style
]

# Max wait time before giving up on a loading model (seconds)
_MAX_LOADING_WAIT = 60


class HuggingFaceProvider(ImageProvider):
    """
    Free image generation via Hugging Face Inference API.

    Works without an API token (heavily rate-limited) or with a free
    HF token for improved limits. All configuration is injected from
    environment variables so the provider can be swapped or tested easily.

    Cold-start handling:
        When a model is loading, HF returns HTTP 503 with an estimated wait time.
        We automatically retry once after that delay (capped at 60s).
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> None:
        self._token = api_token or os.getenv("HF_TOKEN", "")
        self._default_model = (
            model_name or os.getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell")
        )
        self._timeout = timeout or int(os.getenv("HF_TIMEOUT", "120"))

        if not self._token:
            logger.warning(
                "HuggingFaceProvider: HF_TOKEN is not set. "
                "Requests will be severely rate-limited. "
                "Get a free token at https://huggingface.co/settings/tokens"
            )
        else:
            logger.info(
                "HuggingFaceProvider: initialised with token (model=%s)",
                self._default_model,
            )

    # ── Provider interface ─────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "huggingface"

    def supported_modes(self) -> List[ImageGenMode]:
        return [ImageGenMode.TEXT_TO_IMAGE]

    def supported_aspect_ratios(self) -> List[str]:
        return list(_ASPECT_DIMENSIONS.keys())

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "image/png, image/jpeg, image/*",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _call_api(
        self,
        model: str,
        payload: Dict[str, Any],
        allow_retry_on_loading: bool = True,
    ) -> bytes:
        """
        POST to HF Inference API and return raw image bytes.

        Handles:
          - 503 model loading → waits estimated_time and retries once
          - 401/403 → clear auth error
          - 4xx/5xx → descriptive error
        """
        url = f"{_HF_INFERENCE_BASE}/{model}"
        body = json.dumps(payload).encode("utf-8")
        headers = self._build_headers()

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.read()

        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()

            # Model is loading — wait and retry once
            if status == 503 and allow_retry_on_loading:
                try:
                    err_data = json.loads(raw)
                    estimated = min(
                        float(err_data.get("estimated_time", 30)),
                        _MAX_LOADING_WAIT,
                    )
                except (json.JSONDecodeError, ValueError):
                    estimated = 30.0

                logger.info(
                    "HuggingFaceProvider: Model '%s' is loading. "
                    "Waiting %.0fs then retrying...",
                    model, estimated,
                )
                time.sleep(estimated)
                return self._call_api(model, payload, allow_retry_on_loading=False)

            if status in (401, 403):
                raise RuntimeError(
                    f"Hugging Face authentication failed (HTTP {status}). "
                    "Check your HF_TOKEN or that you've accepted the model's license at "
                    f"https://huggingface.co/{model}"
                ) from exc

            try:
                err_msg = json.loads(raw).get("error", raw.decode("utf-8", errors="ignore"))
            except Exception:
                err_msg = raw.decode("utf-8", errors="ignore")[:300]

            raise RuntimeError(
                f"Hugging Face API error (HTTP {status}): {err_msg}"
            ) from exc

        except Exception as exc:
            raise RuntimeError(
                f"Hugging Face network error: {exc}"
            ) from exc

    # ── Generation ─────────────────────────────────────────────────────────────

    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        """
        Generate an image via HF Inference API and return ImageResult.

        Parameters are mapped from the request's visual_brief and generation_params,
        so the caller never needs to know provider-specific field names.
        """
        model = request.model_name or self._default_model
        ar = request.visual_brief.aspect_ratio
        width, height = _ASPECT_DIMENSIONS.get(ar, (1024, 1024))

        # Build HF-specific parameters from our generic generation_params
        # Callers can pass {"num_inference_steps": 30} etc. in generation_params
        hf_params: Dict[str, Any] = {
            "width":  width,
            "height": height,
        }
        if request.negative_prompt:
            hf_params["negative_prompt"] = request.negative_prompt

        # Override with any caller-supplied provider-specific params
        extra = request.generation_params or {}
        hf_params.update({
            k: v for k, v in extra.items()
            if k in {
                "num_inference_steps", "guidance_scale", "seed",
                "scheduler", "strength", "num_images_per_prompt",
            }
        })

        payload = {
            "inputs": request.prompt,
            "parameters": hf_params,
        }

        logger.info(
            "HuggingFaceProvider: Requesting %s | size=%dx%d | prompt_len=%d",
            model, width, height, len(request.prompt),
        )

        start_ms = time.monotonic()
        image_bytes = self._call_api(model, payload)
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        if not image_bytes or len(image_bytes) < 500:
            raise RuntimeError(
                f"Hugging Face returned unexpectedly small response ({len(image_bytes)} bytes). "
                "The model may have returned an error as image bytes."
            )

        # HF returns JPEG by default for most SD models, PNG for some
        # We detect by magic bytes
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            content_type = "image/png"
        elif image_bytes[:2] == b'\xff\xd8':
            content_type = "image/jpeg"
        else:
            content_type = "image/jpeg"  # Safe fallback

        logger.info(
            "HuggingFaceProvider: Received %d bytes in %dms (%s, model=%s)",
            len(image_bytes), elapsed_ms, content_type, model,
        )

        return ImageResult(
            image_bytes=image_bytes,
            content_type=content_type,
            width=width,
            height=height,
            provider_name=self.name,
            model_name=model,
            provider_metadata={
                "hf_model": model,
                "aspect_ratio": ar,
                "has_token": bool(self._token),
                "negative_prompt_used": bool(request.negative_prompt),
                "prompt_chars": len(request.prompt),
            },
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )
