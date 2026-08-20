"""
api/web/image_jobs.py — Background RQ Job Workers for Image Generation.

Runs off the FastAPI main event loop in the image worker process (api/web/image_worker.py).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("trendforge.api.image_jobs")


def run_image_generation_job(
    session_id: str,
    client_name: str,
    post_number: int,
    post_data: Dict[str, Any],
    platform: str = "instagram",
    visual_profile_id: Optional[str] = None,
    reference_image_id: Optional[str] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Background job function executed by the image RQ worker.
    """
    from imaging.service import ImageService
    from imaging.models import ImageAssetStatus
    from memory.redis_session_store import load_conversation, save_conversation

    service = ImageService()
    user_id = None
    if client_name.startswith("user:"):
        try:
            user_id = int(client_name.split(":", 1)[1])
        except (ValueError, IndexError):
            user_id = None

    logger.info(
        "Starting background image job for session=%s, post=%d, ref=%s",
        session_id,
        post_number,
        reference_image_id,
    )

    if reference_image_id:
        asset = service.regenerate_image_to_image(
            reference_asset_id=reference_image_id,
            post_data=post_data,
            session_id=session_id,
            post_number=post_number,
            platform=platform,
            user_id=user_id,
            custom_prompt=custom_prompt,
        )
    else:
        asset = service.generate_text_to_image(
            post_data=post_data,
            session_id=session_id,
            post_number=post_number,
            platform=platform,
            user_id=user_id,
            visual_profile_id=visual_profile_id,
            custom_prompt=custom_prompt,
        )

    if asset.status == ImageAssetStatus.COMPLETED:
        # Attach image asset id to conversation state in Redis for seamless UI hydration
        try:
            conversation = load_conversation(session_id, client_name)
            posts = conversation.get("last_generated_posts", [])
            for p in posts:
                if p.get("number") == post_number:
                    p["image_asset_id"] = asset.id
                    p["image_url"] = f"/images/{asset.id}"
            save_conversation(session_id, client_name, conversation)
        except Exception as e:
            logger.warning("Could not attach image asset %s to conversation: %s", asset.id, e)

        return {
            "status": "completed",
            "asset_id": asset.id,
            "image_url": f"/images/{asset.id}",
            "post_number": post_number,
            "file_size_bytes": asset.file_size_bytes,
        }
    else:
        return {
            "status": "failed",
            "asset_id": asset.id,
            "post_number": post_number,
            "error": asset.error_message or "Unknown generation error",
        }
