"""
imaging/metadata.py — Metadata Repository for Image Assets and Visual Profiles.

Translates between Domain Models (ImageAsset, BrandVisualProfile) and Database
rows in PostgreSQL (api/web/db.py). Includes in-memory fallback for testing
environments where Postgres is not running.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from imaging.models import (
    BrandVisualProfile,
    ImageAsset,
    ImageAssetStatus,
    ImageGenMode,
    StorageBackend,
    VisualBrief,
)

logger = logging.getLogger("trendforge.imaging.metadata")

# In-memory fallbacks when DB is unreachable / in unit test
_MEM_ASSETS: Dict[str, ImageAsset] = {}
_MEM_PROFILES: Dict[str, BrandVisualProfile] = {}


class MetadataRepository:
    """Repository for image assets and visual profiles."""

    def __init__(self, use_db_fallback: bool = True):
        self.use_db_fallback = use_db_fallback

    # ─────────────────────────────────────────────────────────────────────────
    # Image Asset Operations
    # ─────────────────────────────────────────────────────────────────────────

    def save_asset(self, asset: ImageAsset) -> ImageAsset:
        """Persist a new ImageAsset."""
        _MEM_ASSETS[asset.id] = asset

        try:
            from api.web.db import create_image_asset_in_db

            asset_dict = asset.model_dump()
            # Convert Enums to strings for DB storage
            asset_dict["mode"] = asset.mode.value
            asset_dict["status"] = asset.status.value
            asset_dict["storage_backend"] = asset.storage_backend.value
            if asset.visual_brief:
                asset_dict["visual_brief"] = asset.visual_brief.model_dump()

            create_image_asset_in_db(asset_dict)
            logger.debug("Persisted image asset %s to database", asset.id)
        except Exception as e:
            if not self.use_db_fallback:
                raise
            logger.info("DB save skipped for asset %s: %s (cached in memory)", asset.id, e)

        return asset

    def get_asset(self, asset_id: str) -> Optional[ImageAsset]:
        """Retrieve an ImageAsset by ID."""
        try:
            from api.web.db import get_image_asset_from_db

            row = get_image_asset_from_db(asset_id)
            if row:
                brief = VisualBrief.model_validate(row["visual_brief"]) if row.get("visual_brief") else None
                return ImageAsset(
                    id=row["id"],
                    user_id=row.get("user_id"),
                    session_id=row.get("session_id", ""),
                    post_number=row.get("post_number", 1),
                    mode=ImageGenMode(row.get("mode", "text_to_image")),
                    prompt=row.get("prompt", ""),
                    negative_prompt=row.get("negative_prompt", ""),
                    visual_profile_id=row.get("visual_profile_id"),
                    visual_brief=brief,
                    provider_name=row.get("provider_name", "mock"),
                    model_name=row.get("model_name", ""),
                    generation_params=row.get("generation_params") or {},
                    provider_metadata=row.get("provider_metadata") or {},
                    reference_asset_id=row.get("reference_asset_id"),
                    source_post_version=row.get("source_post_version", 1),
                    storage_backend=StorageBackend(row.get("storage_backend", "local")),
                    storage_key=row.get("storage_key", ""),
                    content_type=row.get("content_type", "image/png"),
                    file_size_bytes=row.get("file_size_bytes"),
                    status=ImageAssetStatus(row.get("status", "pending")),
                    error_message=row.get("error_message"),
                    rq_job_id=row.get("rq_job_id"),
                )
        except Exception as e:
            logger.debug("DB lookup failed for asset %s: %s", asset_id, e)

        return _MEM_ASSETS.get(asset_id)

    def update_asset_status(
        self,
        asset_id: str,
        status: ImageAssetStatus,
        error_message: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        storage_key: Optional[str] = None,
        provider_metadata: Optional[dict] = None,
    ) -> bool:
        """Update lifecycle status and output details of an image asset."""
        if asset_id in _MEM_ASSETS:
            asset = _MEM_ASSETS[asset_id]
            asset.status = status
            if error_message is not None:
                asset.error_message = error_message
            if file_size_bytes is not None:
                asset.file_size_bytes = file_size_bytes
            if storage_key is not None:
                asset.storage_key = storage_key
            if provider_metadata is not None:
                asset.provider_metadata.update(provider_metadata)

        try:
            from api.web.db import update_image_asset_status_in_db

            return update_image_asset_status_in_db(
                asset_id=asset_id,
                status=status.value,
                error_message=error_message,
                file_size_bytes=file_size_bytes,
                storage_key=storage_key,
                provider_metadata=provider_metadata,
            )
        except Exception as e:
            logger.debug("DB status update skipped for asset %s: %s", asset_id, e)
            return asset_id in _MEM_ASSETS

    def list_assets_for_session(self, session_id: str) -> List[ImageAsset]:
        """List all image assets associated with a session."""
        try:
            from api.web.db import list_image_assets_for_session_from_db

            rows = list_image_assets_for_session_from_db(session_id)
            if rows:
                assets = []
                for row in rows:
                    assets.append(
                        ImageAsset(
                            id=row["id"],
                            user_id=row.get("user_id"),
                            session_id=row.get("session_id", ""),
                            post_number=row.get("post_number", 1),
                            mode=ImageGenMode(row.get("mode", "text_to_image")),
                            prompt=row.get("prompt", ""),
                            visual_profile_id=row.get("visual_profile_id"),
                            provider_name=row.get("provider_name", "mock"),
                            model_name=row.get("model_name", ""),
                            reference_asset_id=row.get("reference_asset_id"),
                            source_post_version=row.get("source_post_version", 1),
                            storage_backend=StorageBackend(row.get("storage_backend", "local")),
                            storage_key=row.get("storage_key", ""),
                            content_type=row.get("content_type", "image/png"),
                            file_size_bytes=row.get("file_size_bytes"),
                            status=ImageAssetStatus(row.get("status", "pending")),
                            error_message=row.get("error_message"),
                        )
                    )
                return assets
        except Exception as e:
            logger.debug("DB session assets lookup failed for %s: %s", session_id, e)

        return [a for a in _MEM_ASSETS.values() if a.session_id == session_id]

    # ─────────────────────────────────────────────────────────────────────────
    # Visual Profile Operations
    # ─────────────────────────────────────────────────────────────────────────

    def save_profile(self, profile: BrandVisualProfile) -> BrandVisualProfile:
        """Save or create a visual profile."""
        _MEM_PROFILES[profile.id] = profile

        try:
            from api.web.db import create_visual_profile_in_db

            profile_dict = profile.model_dump()
            create_visual_profile_in_db(profile_dict)
            logger.debug("Persisted visual profile %s to database", profile.id)
        except Exception as e:
            logger.info("DB save skipped for profile %s: %s", profile.id, e)

        return profile

    def get_profile(self, profile_id: str) -> Optional[BrandVisualProfile]:
        """Retrieve a visual profile by ID."""
        try:
            from api.web.db import get_visual_profile_from_db

            row = get_visual_profile_from_db(profile_id)
            if row:
                return BrandVisualProfile.model_validate(row)
        except Exception as e:
            logger.debug("DB profile lookup failed for %s: %s", profile_id, e)

        return _MEM_PROFILES.get(profile_id)

    def list_profiles(self, user_id: int) -> List[BrandVisualProfile]:
        """List visual profiles for a user (including system default)."""
        try:
            from api.web.db import list_visual_profiles_from_db

            rows = list_visual_profiles_from_db(user_id)
            if rows:
                return [BrandVisualProfile.model_validate(r) for r in rows]
        except Exception as e:
            logger.debug("DB profiles lookup failed for user %d: %s", user_id, e)

        # In-memory fallback
        matching = [p for p in _MEM_PROFILES.values() if p.user_id == user_id or p.is_default]
        if not matching:
            matching.append(self.get_default_profile())
        return matching

    def get_default_profile(self) -> BrandVisualProfile:
        """Return the default system visual profile."""
        # Try DB first
        try:
            from api.web.db import get_visual_profile_from_db, ensure_default_visual_profile
            ensure_default_visual_profile()
            row = get_visual_profile_from_db("default-trendforge-profile")
            if row:
                profile = BrandVisualProfile.model_validate(row)
                _MEM_PROFILES[profile.id] = profile
                return profile
        except Exception:
            pass

        # Check if default profile is cached
        for p in _MEM_PROFILES.values():
            if p.is_default:
                return p

        default = BrandVisualProfile(
            id="default-trendforge-profile",
            name="TrendForge Standard",
            description="Default informative & clean visual identity",
            is_default=True,
        )
        return self.save_profile(default)
