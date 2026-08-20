"""
imaging/service.py — High-level Image Generation Orchestrator Service.

Coordinates the end-to-end lifecycle of generating, storing, and retrieving
images. Used by FastAPI routes and RQ background workers.

Architecture:
─────────────
Post data + Platform + Brand Profile
  → ContentBrief (via brief_builder or directly)
  → VisualBrief
  → ImageGenRequest (TextToImage, ImageToImage, Inpaint, DesignEdit)
  → ImageProvider (Mock, Gemini Imagen, DALL-E, etc.)
  → AssetStorage (LocalStorage, S3, etc.)
  → MetadataRepository (PostgreSQL / memory)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from imaging.models import (
    BrandVisualProfile,
    ContentBrief,
    ContentTone,
    ImageAsset,
    ImageAssetStatus,
    ImageGenMode,
    ImageJobStatus,
    ImageResult,
    ImageToImageRequest,
    InpaintRequest,
    LayoutType,
    StorageBackend,
    TextToImageRequest,
    VisualBrief,
)
from imaging.brief_builder import build_content_brief, build_visual_brief
from imaging.prompt_builder import build_image_prompt
from imaging.metadata import MetadataRepository
from imaging.providers.base import ImageProvider
from imaging.providers.registry import get_provider
from imaging.storage.base import AssetStorage
from imaging.storage.registry import get_storage

logger = logging.getLogger("trendforge.imaging.service")


class ImageService:
    """Unified service for image generation, retrieval, and lifecycle management."""

    def __init__(
        self,
        provider: Optional[ImageProvider] = None,
        storage: Optional[AssetStorage] = None,
        metadata_repo: Optional[MetadataRepository] = None,
    ):
        self.provider = provider or get_provider("mock")
        self.storage = storage or get_storage("local")
        self.metadata_repo = metadata_repo or MetadataRepository()

    def generate_text_to_image(
        self,
        post_data: Dict[str, Any],
        session_id: str = "",
        post_number: int = 1,
        platform: str = "instagram",
        user_id: Optional[int] = None,
        visual_profile_id: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        generation_params: Optional[Dict[str, Any]] = None,
    ) -> ImageAsset:
        """
        Execute synchronous text-to-image generation for a post.
        (For background/worker execution, this is invoked inside the RQ worker).
        """
        profile = None
        if visual_profile_id:
            profile = self.metadata_repo.get_profile(visual_profile_id)
        if not profile:
            profile = self.metadata_repo.get_default_profile()

        content_brief = build_content_brief(post_data, platform=platform, post_number=post_number)
        visual_brief = build_visual_brief(content_brief, profile=profile, platform=platform)

        # Build prompt using prompt_builder
        derived_prompt, derived_negative_prompt = build_image_prompt(visual_brief)
        prompt = custom_prompt or derived_prompt
        negative_prompt = derived_negative_prompt

        asset_id = str(uuid.uuid4())
        key = self.storage.build_key(user_id=user_id, asset_id=asset_id, extension="png")

        # Create initial asset in PENDING/GENERATING status
        asset = ImageAsset(
            id=asset_id,
            user_id=user_id,
            session_id=session_id,
            post_number=post_number,
            mode=ImageGenMode.TEXT_TO_IMAGE,
            prompt=prompt,
            negative_prompt=negative_prompt,
            visual_profile_id=profile.id,
            visual_brief=visual_brief,
            provider_name=self.provider.name,
            model_name="",
            generation_params=generation_params or {},
            storage_backend=StorageBackend.LOCAL if self.storage.backend_name == "local" else StorageBackend.S3,
            storage_key=key,
            content_type="image/png",
            status=ImageAssetStatus.GENERATING,
        )
        self.metadata_repo.save_asset(asset)

        try:
            req = TextToImageRequest(
                mode=ImageGenMode.TEXT_TO_IMAGE,
                visual_brief=visual_brief,
                provider_name=self.provider.name,
                generation_params=generation_params or {},
                session_id=session_id,
                post_number=post_number,
                user_id=user_id,
                visual_profile_id=profile.id,
                prompt=prompt,
                negative_prompt=negative_prompt,
            )

            result: ImageResult = self.provider.generate(req)

            # Store image in asset storage
            self.storage.save(key, result.image_bytes, content_type=result.content_type)

            # Update asset status
            self.metadata_repo.update_asset_status(
                asset_id=asset.id,
                status=ImageAssetStatus.COMPLETED,
                file_size_bytes=len(result.image_bytes),
                storage_key=key,
                provider_metadata=result.provider_metadata,
            )
            asset.status = ImageAssetStatus.COMPLETED
            asset.file_size_bytes = len(result.image_bytes)
            asset.provider_metadata = result.provider_metadata
            logger.info("Successfully generated and saved image asset %s", asset.id)
            return asset

        except Exception as e:
            logger.exception("Image generation failed for asset %s: %s", asset.id, e)
            self.metadata_repo.update_asset_status(
                asset_id=asset.id,
                status=ImageAssetStatus.FAILED,
                error_message=str(e),
            )
            asset.status = ImageAssetStatus.FAILED
            asset.error_message = str(e)
            return asset

    def regenerate_image_to_image(
        self,
        reference_asset_id: str,
        post_data: Dict[str, Any],
        session_id: str = "",
        post_number: int = 1,
        platform: str = "instagram",
        user_id: Optional[int] = None,
        reference_strength: float = 0.75,
        custom_prompt: Optional[str] = None,
    ) -> ImageAsset:
        """Regenerate an existing image using image_to_image mode."""
        ref_asset = self.metadata_repo.get_asset(reference_asset_id)
        if not ref_asset:
            raise ValueError(f"Reference image asset {reference_asset_id} not found.")

        profile = None
        if ref_asset.visual_profile_id:
            profile = self.metadata_repo.get_profile(ref_asset.visual_profile_id)

        content_brief = build_content_brief(post_data, platform=platform, post_number=post_number)
        visual_brief = build_visual_brief(content_brief, profile=profile, platform=platform)

        derived_prompt, derived_negative_prompt = build_image_prompt(visual_brief)
        prompt = custom_prompt or f"Refined visual update: {derived_prompt}"
        negative_prompt = derived_negative_prompt

        new_asset_id = str(uuid.uuid4())
        key = self.storage.build_key(user_id=user_id, asset_id=new_asset_id, extension="png")

        asset = ImageAsset(
            id=new_asset_id,
            user_id=user_id,
            session_id=session_id,
            post_number=post_number,
            mode=ImageGenMode.IMAGE_TO_IMAGE,
            prompt=prompt,
            negative_prompt=negative_prompt,
            reference_asset_id=reference_asset_id,
            source_post_version=ref_asset.source_post_version + 1,
            visual_profile_id=ref_asset.visual_profile_id,
            visual_brief=visual_brief,
            provider_name=self.provider.name,
            storage_backend=StorageBackend.LOCAL if self.storage.backend_name == "local" else StorageBackend.S3,
            storage_key=key,
            content_type="image/png",
            status=ImageAssetStatus.GENERATING,
        )
        self.metadata_repo.save_asset(asset)

        try:
            req = ImageToImageRequest(
                mode=ImageGenMode.IMAGE_TO_IMAGE,
                visual_brief=visual_brief,
                provider_name=self.provider.name,
                session_id=session_id,
                post_number=post_number,
                user_id=user_id,
                prompt=prompt,
                reference_asset_id=reference_asset_id,
                reference_strength=reference_strength,
            )

            result = self.provider.generate(req)
            self.storage.save(key, result.image_bytes, content_type=result.content_type)
            self.metadata_repo.update_asset_status(
                asset_id=asset.id,
                status=ImageAssetStatus.COMPLETED,
                file_size_bytes=len(result.image_bytes),
                storage_key=key,
                provider_metadata=result.provider_metadata,
            )
            asset.status = ImageAssetStatus.COMPLETED
            asset.file_size_bytes = len(result.image_bytes)
            return asset
        except Exception as e:
            logger.exception("Image regeneration failed for %s: %s", asset.id, e)
            self.metadata_repo.update_asset_status(
                asset_id=asset.id,
                status=ImageAssetStatus.FAILED,
                error_message=str(e),
            )
            asset.status = ImageAssetStatus.FAILED
            asset.error_message = str(e)
            return asset

    def get_asset(self, asset_id: str) -> Optional[ImageAsset]:
        """Get ImageAsset metadata by ID."""
        return self.metadata_repo.get_asset(asset_id)

    def get_asset_bytes(self, asset_id: str) -> Optional[Tuple[bytes, str]]:
        """Retrieve raw image bytes and content-type for an asset."""
        asset = self.get_asset(asset_id)
        if not asset or not asset.storage_key:
            return None

        data = self.storage.get(asset.storage_key)
        if not data:
            return None
        return data, asset.content_type

    def list_session_assets(self, session_id: str) -> List[ImageAsset]:
        """List all image assets generated in a session."""
        return self.metadata_repo.list_assets_for_session(session_id)
