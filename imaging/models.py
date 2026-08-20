"""
imaging/models.py — Core domain models for the TrendForge image generation subsystem.

Design intent
─────────────
These models form the structured intermediate representation (SIR) that prevents
the system from naively concatenating post text into image prompts.

The pipeline is:

  Raw post data
    → ContentBrief   (WHAT the content says — extracted, structured)
    → VisualBrief    (HOW it should look — platform + brand + intent)
    → ImageGenRequest (provider-ready request, mode-specific)
    → ImageResult    (raw output from provider)
    → ImageAsset     (persisted, with all generation metadata)

Generation modes are first-class citizens, not an afterthought:

  text_to_image  — Generate from visual brief + prompt. No reference.
  image_to_image — Use a reference image + prompt to alter/extend it.
  inpaint        — Edit a masked region of an existing image.
  design_edit    — Structural design changes (future: user-driven canvas).

Each mode has its own request model that extends BaseImageGenRequest. Adding a
new mode means adding one model class here and one provider method — nothing
else needs to change.

No values are hardcoded. Providers, storage backends, and visual profiles are
all loaded from configuration and the registry at runtime.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums — explicit, extensible value sets
# ─────────────────────────────────────────────────────────────────────────────

class ImageGenMode(str, enum.Enum):
    """Image generation mode. New modes are added here and in the provider."""
    TEXT_TO_IMAGE  = "text_to_image"   # Prompt → image from scratch
    IMAGE_TO_IMAGE = "image_to_image"  # Reference image + prompt → modified image
    INPAINT        = "inpaint"          # Masked region + prompt → filled region
    DESIGN_EDIT    = "design_edit"      # Future: user-driven structural edits


class ImageAssetStatus(str, enum.Enum):
    """Lifecycle status of an image asset."""
    PENDING    = "pending"     # Created, not yet queued
    QUEUED     = "queued"      # In RQ queue
    GENERATING = "generating"  # Worker picked up, provider call in-flight
    COMPLETED  = "completed"   # Provider returned; asset saved to storage
    FAILED     = "failed"      # Terminal failure


class ContentTone(str, enum.Enum):
    """Tone of the content — influences visual mood selection."""
    INFORMATIVE  = "informative"
    INSPIRATIONAL = "inspirational"
    TECHNICAL    = "technical"
    CASUAL       = "casual"
    PROFESSIONAL = "professional"
    URGENT       = "urgent"


class LayoutType(str, enum.Enum):
    """Visual layout archetype. Drives prompt construction."""
    TEXT_CARD          = "text_card"         # Clean typographic card
    DIAGRAM            = "diagram"            # Flow / architecture diagram
    PHOTO_REALISTIC    = "photo_realistic"   # Real-world scene
    ABSTRACT_TECH      = "abstract_tech"     # Abstract geometric/tech art
    MINIMAL_CLEAN      = "minimal_clean"     # Whitespace-heavy, minimal
    BOLD_CONTRAST      = "bold_contrast"     # High contrast, attention-grabbing
    INFORMATIVE_INFOGRAPHIC = "infographic"  # Data/process visualization
    THUMBNAIL          = "thumbnail"          # Platform: YouTube thumbnail


class StorageBackend(str, enum.Enum):
    """Storage backend identifier. Matches registry key in storage/registry.py."""
    LOCAL = "local"
    S3    = "s3"
    GCS   = "gcs"


# ─────────────────────────────────────────────────────────────────────────────
# Brand Visual Profile
# ─────────────────────────────────────────────────────────────────────────────

class ColorPalette(BaseModel):
    """A named set of colors for a brand visual profile."""
    primary: str   = "#1a1a2e"   # Dominant background or main color
    secondary: str = "#16213e"   # Supporting color
    accent: str    = "#e94560"   # Highlight / CTA color
    text: str      = "#ffffff"   # Primary text on images
    surface: str   = "#0f3460"   # Card/panel color

    model_config = {"extra": "allow"}  # Allow brand-specific extensions


class PlatformVisualOverride(BaseModel):
    """Per-platform overrides for a visual profile."""
    aspect_ratio: Optional[str]   = None   # Overrides platform default
    layout_type: Optional[str]    = None   # Overrides profile default
    color_palette: Optional[ColorPalette] = None
    max_text_overlay_words: Optional[int] = None

    model_config = {"extra": "allow"}


class BrandVisualProfile(BaseModel):
    """
    Reusable brand identity for image generation.

    Stored in the `visual_profiles` Postgres table and referenced by ID on
    ImageGenRequest. A profile provides visual consistency across posts while
    still allowing per-platform overrides.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int]   = None
    name: str                = "Default TrendForge Style"
    description: str         = ""

    # Visual identity
    color_palette: ColorPalette              = Field(default_factory=ColorPalette)
    typography_style: str                    = "minimal-sans"
    # e.g. "minimal-sans", "tech-mono", "bold-display", "editorial"
    visual_mood: str                         = "clean-informative"
    # e.g. "clean-informative", "bold-contrast", "dark-tech", "light-minimal"
    default_layout: LayoutType               = LayoutType.MINIMAL_CLEAN

    # Platform-specific tweaks on top of the base profile
    platform_overrides: dict[str, PlatformVisualOverride] = Field(default_factory=dict)

    # Meta
    is_default: bool     = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def for_platform(self, platform: str) -> "BrandVisualProfile":
        """
        Return a copy of this profile with platform overrides applied.
        Leaves the original unchanged.
        """
        override = self.platform_overrides.get(platform)
        if not override:
            return self
        merged = self.model_copy(deep=True)
        if override.color_palette:
            merged.color_palette = override.color_palette
        if override.layout_type:
            merged.default_layout = LayoutType(override.layout_type)
        return merged


# ─────────────────────────────────────────────────────────────────────────────
# Content Brief  — WHAT the content says
# ─────────────────────────────────────────────────────────────────────────────

class ContentBrief(BaseModel):
    """
    Structured extraction from a generated post.

    This is the single source of truth for what the content SAYS. It is built
    by imaging/brief_builder.py from the raw post dict returned by the text
    generation pipeline.

    It is deliberately NOT a visual specification — that lives in VisualBrief.
    The separation exists so the same content can be rendered for different
    platforms/styles without regenerating text.
    """
    # Core identity
    topic: str                   = ""
    title: str                   = ""
    subtitle: Optional[str]      = None

    # Key informational elements (preserved — not lost in visual transformation)
    key_concepts: list[str]      = Field(default_factory=list)
    # e.g. ["LangGraph", "RAG pipeline", "vector embeddings"]
    technical_elements: list[str] = Field(default_factory=list)
    # e.g. ["Python", "Qdrant", "HuggingFace Embeddings"]
    key_facts: list[str]         = Field(default_factory=list)
    # Explicit facts the user provided that MUST appear visually if rendered

    # Content shape
    content_intent: str          = "showcase"
    # "showcase" | "educate" | "news" | "inspire" | "review"
    tone: ContentTone            = ContentTone.INFORMATIVE
    audience: str                = "developers"

    # Source signal
    source_url: Optional[str]    = None
    source_label: Optional[str]  = None

    # Platform context
    platform: str                = "instagram"
    post_number: int             = 1


# ─────────────────────────────────────────────────────────────────────────────
# Visual Brief — HOW it should look
# ─────────────────────────────────────────────────────────────────────────────

class VisualBrief(BaseModel):
    """
    Platform + brand + intent → visual specification.

    Built by imaging/brief_builder.py. The bridge between what content says
    and how the image provider will render it.

    The image prompt is NOT stored here — it is derived from this brief by
    imaging/prompt_builder.py. This separation allows the prompt to be
    regenerated for different providers without rebuilding the brief.
    """
    content_brief: ContentBrief

    # Visual direction
    visual_mood: str                  = "clean-informative"
    layout_type: LayoutType           = LayoutType.MINIMAL_CLEAN
    color_direction: str              = "dark tech palette with teal accent"

    # Text overlay — ONLY when it adds genuine value
    text_overlay_title: Optional[str]  = None   # Main text on image
    text_overlay_subtitle: Optional[str] = None
    include_source_label: bool         = False   # Show "from GitHub" etc.
    max_text_overlay_words: int        = 10

    # Emphasis and exclusion
    emphasis_elements: list[str]       = Field(default_factory=list)
    # e.g. ["Python logo", "terminal screenshot", "code snippet"]
    avoid_elements: list[str]          = Field(default_factory=list)
    # e.g. ["emojis", "clip art", "faces", "watermarks"]

    # Platform constraints
    aspect_ratio: str                  = "4:5"
    # "4:5" for IG feed, "16:9" for YT thumbnail, "1:1" for square, etc.
    platform_constraints: dict[str, Any] = Field(default_factory=dict)

    # Profile reference (optional — profile already applied to derive the above)
    visual_profile_id: Optional[str]   = None


# ─────────────────────────────────────────────────────────────────────────────
# Image Generation Requests — one per mode
# ─────────────────────────────────────────────────────────────────────────────

class BaseImageGenRequest(BaseModel):
    """
    Shared fields for all image generation request modes.

    Subclass this for each new mode. The provider receives the concrete
    subclass and dispatches based on its type. Adding a new mode = add a
    subclass here + handle it in the provider. No other changes required.
    """
    model_config = {"protected_namespaces": ()}

    mode: ImageGenMode
    visual_brief: VisualBrief

    # Provider routing
    provider_name: str           = "mock"
    # e.g. "gemini_imagen", "dalle3", "flux", "mock"
    model_name: str              = ""
    # Provider-specific model identifier, empty = provider default

    # Generation parameters (provider-specific, typed as open dict for flexibility)
    generation_params: dict[str, Any] = Field(default_factory=dict)
    # e.g. {"seed": 42, "steps": 30, "guidance_scale": 7.5}

    # Traceability
    session_id: str              = ""
    post_number: int             = 1
    user_id: Optional[int]       = None
    visual_profile_id: Optional[str] = None


class TextToImageRequest(BaseImageGenRequest):
    """
    Mode: TEXT_TO_IMAGE
    Generate an image purely from text prompt. No reference image.
    This is the default mode for new posts.
    """
    mode: ImageGenMode = ImageGenMode.TEXT_TO_IMAGE

    # Built by prompt_builder.py from visual_brief — never set manually
    prompt: str = ""
    negative_prompt: str = ""


class ImageToImageRequest(BaseImageGenRequest):
    """
    Mode: IMAGE_TO_IMAGE
    Use an existing image as reference and modify it via prompt.
    Used for post regeneration when a previous image exists.
    """
    mode: ImageGenMode = ImageGenMode.IMAGE_TO_IMAGE

    prompt: str              = ""
    negative_prompt: str     = ""
    reference_asset_id: str  = ""   # ID of the existing ImageAsset to use as base
    reference_strength: float = 0.75
    # 0.0 = ignore reference entirely, 1.0 = barely change it


class InpaintRequest(BaseImageGenRequest):
    """
    Mode: INPAINT
    Edit a masked region of an existing image.
    """
    mode: ImageGenMode = ImageGenMode.INPAINT

    prompt: str              = ""
    negative_prompt: str     = ""
    reference_asset_id: str  = ""
    mask_asset_id: str       = ""   # Asset ID of the mask image (black/white PNG)


class DesignEditRequest(BaseImageGenRequest):
    """
    Mode: DESIGN_EDIT
    Future: User-driven structural edits (canvas-based editing).
    Placeholder for the interface — implementation deferred.
    """
    mode: ImageGenMode = ImageGenMode.DESIGN_EDIT

    # Will be defined when canvas editing is designed
    edit_instructions: dict[str, Any] = Field(default_factory=dict)


# Union type — provider receives this
ImageGenRequest = TextToImageRequest | ImageToImageRequest | InpaintRequest | DesignEditRequest


# ─────────────────────────────────────────────────────────────────────────────
# Provider Result
# ─────────────────────────────────────────────────────────────────────────────

class ImageResult(BaseModel):
    """
    Raw output from an image provider.

    Provider implementations return this. The service layer is responsible
    for persisting the bytes to storage and recording metadata.
    """
    model_config = {"arbitrary_types_allowed": True, "protected_namespaces": ()}

    image_bytes: bytes
    content_type: str              = "image/png"
    # "image/png" | "image/jpeg" | "image/webp"
    width: Optional[int]           = None
    height: Optional[int]          = None
    provider_name: str             = ""
    model_name: str                = ""
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    # Raw provider response data — stored as-is for debugging / future use
    tokens_used: int               = 0       # if provider bills by token
    generation_time_ms: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Persisted Image Asset
# ─────────────────────────────────────────────────────────────────────────────

class ImageAsset(BaseModel):
    """
    A persisted, generated image. Corresponds to one row in `image_assets`.

    An asset is immutable once completed — editing or regenerating creates
    a NEW asset with reference_asset_id pointing to the previous one.
    This enables full version history without overwriting anything.
    """
    model_config = {"protected_namespaces": ()}

    id: str                        = Field(default_factory=lambda: str(uuid.uuid4()))

    # Ownership / context
    user_id: Optional[int]         = None
    session_id: str                = ""
    post_number: int               = 1

    # Generation inputs (for full reproducibility)
    mode: ImageGenMode             = ImageGenMode.TEXT_TO_IMAGE
    prompt: str                    = ""
    negative_prompt: str           = ""
    visual_profile_id: Optional[str] = None
    visual_brief: Optional[VisualBrief] = None  # Serialized for full audit trail
    provider_name: str             = ""
    model_name: str                = ""
    generation_params: dict[str, Any] = Field(default_factory=dict)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    # Version lineage
    reference_asset_id: Optional[str] = None   # Previous asset if regenerated
    source_post_version: int       = 1
    # Incremented each time the parent post text is edited

    # Storage
    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_key: str               = ""
    # Opaque key understood by the storage backend (e.g. relative path or S3 key)
    content_type: str              = "image/png"
    file_size_bytes: Optional[int] = None

    # Lifecycle
    status: ImageAssetStatus       = ImageAssetStatus.PENDING
    error_message: Optional[str]   = None
    rq_job_id: Optional[str]       = None  # RQ job ID for status lookups

    # Timestamps
    created_at: datetime           = Field(default_factory=datetime.utcnow)
    updated_at: datetime           = Field(default_factory=datetime.utcnow)

    def is_outdated(self, current_post_version: int) -> bool:
        """True if the parent post has been edited since this image was generated."""
        return current_post_version > self.source_post_version


# ─────────────────────────────────────────────────────────────────────────────
# Job status (ephemeral — lives in RQ, not Postgres)
# ─────────────────────────────────────────────────────────────────────────────

class ImageJobStatus(BaseModel):
    """
    Returned by GET /images/status/{job_id}.
    Bridges RQ job status → API response without coupling routes to RQ directly.
    """
    job_id: str
    status: ImageAssetStatus       = ImageAssetStatus.QUEUED
    asset_id: Optional[str]        = None
    error: Optional[str]           = None
    progress_message: str          = ""
