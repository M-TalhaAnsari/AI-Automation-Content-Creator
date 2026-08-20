"""
api/web/image_schemas.py — Pydantic Request & Response Data Contracts for Image Endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    """Request payload to generate an image for a single post."""
    session_id: str
    post_number: int = 1
    post_data: Dict[str, Any] = Field(
        ...,
        description="The full post dictionary containing title, hook, summary, caption, and platform."
    )
    platform: Optional[str] = "instagram"
    visual_profile_id: Optional[str] = None
    reference_image_id: Optional[str] = Field(
        None,
        description="Optional asset_id of an existing image to use as reference (image-to-image regeneration)."
    )
    custom_prompt: Optional[str] = None


class BatchImageItem(BaseModel):
    """Single item inside a batch image generation request."""
    post_number: int
    post_data: Dict[str, Any]
    reference_image_id: Optional[str] = None
    custom_prompt: Optional[str] = None


class BatchImageGenerateRequest(BaseModel):
    """Request payload to generate images for multiple posts in one call."""
    session_id: str
    posts: List[BatchImageItem]
    platform: Optional[str] = "instagram"
    visual_profile_id: Optional[str] = None


class ImageJobResponse(BaseModel):
    """Returned immediately when an image job is enqueued."""
    status: str = "queued"
    job_id: str
    post_number: int = 1


class BatchImageJobResponse(BaseModel):
    """Returned when a batch image generation job is enqueued."""
    status: str = "queued"
    jobs: List[ImageJobResponse]


class ImageJobStatusResponse(BaseModel):
    """Response returned when polling GET /images/status/{job_id}."""
    status: str
    job_id: str
    post_number: Optional[int] = 1
    asset_id: Optional[str] = None
    image_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    detail: Optional[str] = None


class ImageAssetMeta(BaseModel):
    """Metadata response for a completed image asset."""
    id: str
    session_id: str
    post_number: int
    mode: str
    prompt: str
    negative_prompt: Optional[str] = None
    visual_profile_id: Optional[str] = None
    provider_name: str
    model_name: Optional[str] = None
    reference_asset_id: Optional[str] = None
    source_post_version: int = 1
    storage_backend: str = "local"
    storage_key: str
    content_type: str = "image/png"
    file_size_bytes: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    image_url: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VisualProfileCreateRequest(BaseModel):
    """Request to create a new BrandVisualProfile."""
    name: str
    description: Optional[str] = ""
    color_palette: Optional[Dict[str, str]] = None
    typography_style: Optional[str] = "minimal-sans"
    visual_mood: Optional[str] = "clean-informative"
    default_layout: Optional[str] = "minimal_clean"
    platform_overrides: Optional[Dict[str, Any]] = None


class VisualProfileResponse(BaseModel):
    """Response representing a BrandVisualProfile."""
    id: str
    name: str
    description: str
    color_palette: Dict[str, Any]
    typography_style: str
    visual_mood: str
    default_layout: str
    platform_overrides: Dict[str, Any]
    is_default: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
