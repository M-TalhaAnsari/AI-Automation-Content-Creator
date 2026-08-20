"""
imaging/providers/base.py — Abstract Base Class for all Image Providers.

Design intent:
─────────────
Every image generation engine (Gemini Imagen, DALL-E, Flux, Mock, etc.)
inherits from `ImageProvider`.

The interface supports multiple generation modes:
  - text_to_image
  - image_to_image
  - inpaint
  - design_edit

Providers can declare which modes and aspect ratios they support.
The base class implements dispatching based on `request.mode`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from imaging.models import (
    DesignEditRequest,
    ImageGenMode,
    ImageGenRequest,
    ImageResult,
    ImageToImageRequest,
    InpaintRequest,
    TextToImageRequest,
)


class ImageProvider(ABC):
    """Abstract interface for image generation engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g. 'mock', 'gemini_imagen', 'dalle3')."""
        raise NotImplementedError

    @abstractmethod
    def supported_aspect_ratios(self) -> List[str]:
        """List of supported aspect ratios, e.g. ['1:1', '4:5', '16:9', '9:16']."""
        raise NotImplementedError

    def supports_mode(self, mode: ImageGenMode) -> bool:
        """Check whether this provider supports the given generation mode."""
        return mode in self.supported_modes()

    def supported_modes(self) -> List[ImageGenMode]:
        """List of supported modes. Default is [TEXT_TO_IMAGE]. Override if more are supported."""
        return [ImageGenMode.TEXT_TO_IMAGE]

    def generate(self, request: ImageGenRequest) -> ImageResult:
        """
        Main entry point for generating images.
        Dispatches to mode-specific methods based on request.mode.
        """
        if not self.supports_mode(request.mode):
            raise NotImplementedError(
                f"Provider '{self.name}' does not support mode '{request.mode.value}'"
            )

        if isinstance(request, TextToImageRequest):
            return self.generate_text_to_image(request)
        elif isinstance(request, ImageToImageRequest):
            return self.generate_image_to_image(request)
        elif isinstance(request, InpaintRequest):
            return self.generate_inpaint(request)
        elif isinstance(request, DesignEditRequest):
            return self.generate_design_edit(request)
        else:
            raise ValueError(f"Unsupported request type: {type(request)}")

    @abstractmethod
    def generate_text_to_image(self, request: TextToImageRequest) -> ImageResult:
        """Generate image from text prompt / visual brief."""
        raise NotImplementedError

    def generate_image_to_image(self, request: ImageToImageRequest) -> ImageResult:
        """Generate/modify image with reference image base."""
        raise NotImplementedError(f"Provider '{self.name}' does not implement image_to_image.")

    def generate_inpaint(self, request: InpaintRequest) -> ImageResult:
        """Generate/inpaint masked region."""
        raise NotImplementedError(f"Provider '{self.name}' does not implement inpaint.")

    def generate_design_edit(self, request: DesignEditRequest) -> ImageResult:
        """Apply structural / user design edit."""
        raise NotImplementedError(f"Provider '{self.name}' does not implement design_edit.")
