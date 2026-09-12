"""api/web/services/usage_service.py -- Daily generation quota tracking & enforcement.

Ensures users adhere to tier limits (e.g. 15 posts/day for free tier)
with calendar-day tracking (UTC midnight reset) and atomic incrementing in PostgreSQL.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional

from api.web import db
from api.web.errors.exceptions import TierLimitExceededError, TierFeatureComingSoon
from api.web.services.tier_service import get_tier_config, TierConfig

logger = logging.getLogger("aiflick.usage")


def get_next_utc_reset_iso() -> str:
    """Calculates the upcoming midnight UTC reset timestamp in ISO 8601."""
    now_utc = datetime.now(timezone.utc)
    next_reset = (now_utc + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_reset.isoformat()


def get_user_daily_usage(user_id: int) -> Dict[str, int]:
    """Returns today's post and image generation counts for a user."""
    try:
        return db.get_daily_usage(user_id)
    except Exception as e:
        logger.error("Failed to fetch daily usage for user %s: %s", user_id, e)
        return {"posts_generated": 0, "images_generated": 0}


def check_post_quota(
    user_id: int,
    tier_id: Optional[str] = "free",
    requested_posts: int = 1,
) -> None:
    """
    Validates if user has remaining quota for the requested number of posts.
    Raises TierLimitExceededError (HTTP 429) if quota exhausted.
    """
    tier = get_tier_config(tier_id)

    # Unlimited tier check
    if tier.unlimited_posts:
        return

    usage = get_user_daily_usage(user_id)
    posts_used = usage.get("posts_generated", 0)
    post_limit = tier.daily_post_limit

    # Quota check
    if posts_used + requested_posts > post_limit:
        resets_at = get_next_utc_reset_iso()
        remaining = max(0, post_limit - posts_used)
        raise TierLimitExceededError(
            message=(
                f"Daily generation quota exceeded ({posts_used}/{post_limit} posts used today). "
                f"Your quota resets at {resets_at}."
            ),
            used=posts_used,
            limit=post_limit,
            tier=tier.id,
            resets_at=resets_at,
            resource="posts",
        )


def check_image_quota(
    user_id: int,
    tier_id: Optional[str] = "free",
    daily_limit: int = 30,
) -> None:
    """Validates if user has remaining quota for visual studio images."""
    usage = get_user_daily_usage(user_id)
    images_used = usage.get("images_generated", 0)

    if images_used >= daily_limit:
        resets_at = get_next_utc_reset_iso()
        raise TierLimitExceededError(
            message=f"Daily image generation quota reached ({images_used}/{daily_limit}). Resets at {resets_at}.",
            used=images_used,
            limit=daily_limit,
            tier=tier_id or "free",
            resets_at=resets_at,
            resource="images",
        )


def record_post_generation(user_id: int, count: int = 1) -> Dict[str, int]:
    """Atomically increments user's daily post count in PostgreSQL."""
    try:
        return db.increment_daily_posts(user_id, count=count)
    except Exception as e:
        logger.error("Failed to increment daily posts for user %s: %s", user_id, e)
        return {"posts_generated": 0, "images_generated": 0}


def record_image_generation(user_id: int, count: int = 1) -> Dict[str, int]:
    """Atomically increments user's daily image count in PostgreSQL."""
    try:
        return db.increment_daily_images(user_id, count=count)
    except Exception as e:
        logger.error("Failed to increment daily images for user %s: %s", user_id, e)
        return {"posts_generated": 0, "images_generated": 0}
