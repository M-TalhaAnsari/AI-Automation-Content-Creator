"""
imaging/providers/mock.py — Mock Image Provider for testing and local development.

Produces valid PNG images without making external API calls. Renders a clean,
styled canvas with post title, platform, and mode info to make debugging easy.
"""

from __future__ import annotations

import io
import time
from typing import List

from PIL import Image, ImageDraw

from imaging.models import (
    DesignEditRequest,
    ImageGenMode,
    ImageResult,
    ImageToImageRequest,
    InpaintRequest,
    TextToImageRequest,
)
from imaging.providers.base import ImageProvider


def _aspect_ratio_to_dimensions(aspect_ratio: str) -> tuple[int, int]:
    """Map aspect ratio string to concrete pixel dimensions."""
    mapping = {
        "1:1": (1024, 1024),
        "4:5": (1080, 1350),  # Instagram portrait
        "16:9": (1280, 720),  # YouTube landscape
        "9:16": (720, 1280),  # Story / Reels / Shorts
        "4:3": (1024, 768),
        "3:4": (768, 1024),
    }
    return mapping.get(aspect_ratio, (1080, 1080))


class MockImageProvider(ImageProvider):
    """
    Mock image provider for testing without external API dependencies.
    Generates synthetic PNGs with metadata rendered on canvas.
    """

    @property
    def name(self) -> str:
        return "mock"

    def supported_modes(self) -> List[ImageGenMode]:
        return [
            ImageGenMode.TEXT_TO_IMAGE,
            ImageGenMode.IMAGE_TO_IMAGE,
            ImageGenMode.INPAINT,
            ImageGenMode.DESIGN_EDIT,
        ]

    def supported_aspect_ratios(self) -> List[str]:
        return ["1:1", "4:5", "16:9", "9:16", "4:3", "3:4"]

    def _generate_canvas(
        self,
        width: int,
        height: int,
        bg_color: tuple[int, int, int],
        title: str,
        subtitle: str,
        extra_lines: list[str],
    ) -> bytes:
        start_time = time.time()
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw a subtle gradient-like rectangle accent
        accent_color = (233, 69, 96)  # TrendForge red/coral accent
        draw.rectangle([(0, 0), (width, 8)], fill=accent_color)
        draw.rectangle([(0, height - 8), (width, height)], fill=accent_color)

        # Draw border
        draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(60, 70, 90), width=2)

        # Write text
        y = 60
        draw.text((40, y), "TRENDFORGE MOCK IMAGE GENERATOR", fill=accent_color)
        y += 40

        draw.text((40, y), f"Title: {title[:50]}", fill=(255, 255, 255))
        y += 40

        if subtitle:
            draw.text((40, y), f"Topic: {subtitle[:50]}", fill=(180, 190, 210))
            y += 35

        for line in extra_lines:
            draw.text((40, y), line[:70], fill=(140, 150, 170))
            y += 30

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        start_time = time.time()
        w, h = _aspect_ratio_to_dimensions(request.visual_brief.aspect_ratio)
        title = request.visual_brief.content_brief.title or "Untitled Post"
        topic = request.visual_brief.content_brief.topic or ""
        platform = request.visual_brief.content_brief.platform

        png_bytes = self._generate_canvas(
            width=w,
            height=h,
            bg_color=(26, 26, 46),
            title=title,
            subtitle=topic,
            extra_lines=[
                f"Mode: TEXT_TO_IMAGE",
                f"Platform: {platform} ({request.visual_brief.aspect_ratio})",
                f"Mood: {request.visual_brief.visual_mood}",
                f"Layout: {request.visual_brief.layout_type.value}",
                f"Prompt: {request.prompt[:60]}...",
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ImageResult(
            image_bytes=png_bytes,
            content_type="image/png",
            width=w,
            height=h,
            provider_name=self.name,
            model_name="mock-canvas-v1",
            provider_metadata={"mock": True, "prompt_length": len(request.prompt)},
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )

    def generate_image_to_image(self, request: ImageToImageRequest) -> ImageResult:
        start_time = time.time()
        w, h = _aspect_ratio_to_dimensions(request.visual_brief.aspect_ratio)
        title = request.visual_brief.content_brief.title or "Regenerated Post"
        topic = request.visual_brief.content_brief.topic or ""

        png_bytes = self._generate_canvas(
            width=w,
            height=h,
            bg_color=(22, 33, 62),  # Slightly different bg for i2i
            title=title,
            subtitle=topic,
            extra_lines=[
                f"Mode: IMAGE_TO_IMAGE (Strength: {request.reference_strength})",
                f"Ref Asset ID: {request.reference_asset_id}",
                f"Platform: {request.visual_brief.content_brief.platform}",
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ImageResult(
            image_bytes=png_bytes,
            content_type="image/png",
            width=w,
            height=h,
            provider_name=self.name,
            model_name="mock-i2i-v1",
            provider_metadata={"mock": True, "ref": request.reference_asset_id},
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )

    def generate_inpaint(self, request: InpaintRequest) -> ImageResult:
        start_time = time.time()
        w, h = _aspect_ratio_to_dimensions(request.visual_brief.aspect_ratio)
        title = request.visual_brief.content_brief.title or "Inpainted Post"

        png_bytes = self._generate_canvas(
            width=w,
            height=h,
            bg_color=(15, 52, 96),
            title=title,
            subtitle="Inpainting",
            extra_lines=[
                f"Mode: INPAINT",
                f"Ref: {request.reference_asset_id}",
                f"Mask: {request.mask_asset_id}",
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ImageResult(
            image_bytes=png_bytes,
            content_type="image/png",
            width=w,
            height=h,
            provider_name=self.name,
            model_name="mock-inpaint-v1",
            provider_metadata={"mock": True},
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )

    def generate_design_edit(self, request: DesignEditRequest) -> ImageResult:
        start_time = time.time()
        w, h = _aspect_ratio_to_dimensions(request.visual_brief.aspect_ratio)
        title = request.visual_brief.content_brief.title or "Edited Design"

        png_bytes = self._generate_canvas(
            width=w,
            height=h,
            bg_color=(30, 40, 60),
            title=title,
            subtitle="Design Edit",
            extra_lines=[
                f"Mode: DESIGN_EDIT",
                f"Instructions: {list(request.edit_instructions.keys())}",
            ],
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        return ImageResult(
            image_bytes=png_bytes,
            content_type="image/png",
            width=w,
            height=h,
            provider_name=self.name,
            model_name="mock-design-v1",
            provider_metadata={"mock": True},
            tokens_used=0,
            generation_time_ms=elapsed_ms,
        )
