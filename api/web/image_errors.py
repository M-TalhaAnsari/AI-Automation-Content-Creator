"""
api/web/image_errors.py — Custom Exceptions and Error Mappings for the Image Subsystem.
"""

from __future__ import annotations

from typing import Optional
from fastapi import HTTPException, status


class ImageServiceError(Exception):
    """Base exception for image subsystem errors."""
    def __init__(self, message: str, status_code: int = 500, code: str = "image_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ImageNotFoundError(ImageServiceError):
    """Raised when an requested image asset does not exist."""
    def __init__(self, asset_id: str):
        super().__init__(
            message=f"Image asset '{asset_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="image_not_found",
        )


class ImageJobNotFoundError(ImageServiceError):
    """Raised when an RQ image generation job is not found or expired."""
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Image job '{job_id}' not found or has expired.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="image_job_not_found",
        )


class VisualProfileNotFoundError(ImageServiceError):
    """Raised when a requested visual profile is not found."""
    def __init__(self, profile_id: str):
        super().__init__(
            message=f"Visual profile '{profile_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="profile_not_found",
        )


class ImageGenerationFailedError(ImageServiceError):
    """Raised when an image provider fails during generation."""
    def __init__(self, detail: str):
        super().__init__(
            message=f"Image generation failed: {detail}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="generation_failed",
        )


def to_http_exception(err: ImageServiceError) -> HTTPException:
    """Convert an ImageServiceError into a FastAPI HTTPException."""
    return HTTPException(
        status_code=err.status_code,
        detail={"message": err.message, "code": err.code},
    )
