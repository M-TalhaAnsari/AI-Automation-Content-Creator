"""api/web/middleware/tier_guard.py -- Daily quota & tier guard FastAPI dependencies.

Protects LLM and image generation endpoints from exceeding daily plan quotas.
Also ensures Phase 2 paid tiers or premium features gracefully return 'coming soon'
status codes (503) while keeping the Free tier 100% operational.
"""
import logging
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, status

from api.web import anon_trial, db
from api.web.dependencies.auth_deps import verify_identity, get_current_user_id
from api.web.errors.exceptions import (
    TierLimitExceededError,
    TierFeatureComingSoon,
    AuthorizationError,
)
from api.web.services.usage_service import (
    check_post_quota,
    check_image_quota,
    get_next_utc_reset_iso,
)

logger = logging.getLogger("aiflick.tier_guard")


async def enforce_post_quota(
    request: Request,
    client_name: str = Depends(verify_identity),
) -> None:
    """
    Enforces daily post generation quotas:
    1. Authenticated users: Checks user_daily_usage table against their tier quota.
       Raises TierLimitExceededError (HTTP 429) when exhausted.
    2. Anonymous guests: Checks Redis anon_trial limits (3 messages / 3000 tokens).
       Raises HTTPException (HTTP 403, detail='signup_required') when exhausted.
    """
    if client_name.startswith("user:"):
        user_id = get_current_user_id(client_name)
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found",
            )

        tier_id = user.get("tier", "free")

        # Parse requested post count if available in JSON body
        requested_count = 1
        try:
            body_bytes = await request.body()
            if body_bytes:
                import json
                data = json.loads(body_bytes)
                requested_count = int(data.get("posts", 1))
        except Exception:
            requested_count = 1

        # Check quota against PostgreSQL daily usage table
        check_post_quota(
            user_id=user_id,
            tier_id=tier_id,
            requested_posts=requested_count,
        )

    elif client_name.startswith("anon:"):
        anon_id = client_name.split(":", 1)[1]
        if anon_trial.is_over_limit(anon_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="signup_required",
            )


def require_tier(required_tier: str):
    """
    Dependency factory to restrict an endpoint to a specific tier or higher.
    For Phase 2, if a non-free tier is required, raises TierFeatureComingSoon.
    """
    async def _tier_dependency(
        client_name: str = Depends(verify_identity),
    ) -> str:
        if not client_name.startswith("user:"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this feature",
            )

        user_id = get_current_user_id(client_name)
        user = db.get_user_by_id(user_id)
        current_tier = user.get("tier", "free") if user else "free"

        # Phase 2 guard: non-free tiers are coming soon
        if required_tier in ("creator", "agency"):
            raise TierFeatureComingSoon(
                message=f"The {required_tier.title()} feature is coming soon in Phase 2!",
                feature=required_tier,
            )

        return current_tier

    return _tier_dependency
