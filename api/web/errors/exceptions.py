"""api/web/errors/exceptions.py -- Centralized custom exception catalogue for AIFlick.

All domain-level errors are defined here so routes and services can raise
typed exceptions instead of scattering bare HTTPException calls everywhere.
The FastAPI handlers in handlers.py convert these to proper JSON responses.
"""
from typing import Optional


class AIFlickError(Exception):
    """Base class for all AIFlick domain errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: Optional[str] = None):
        self.message = message or self.__class__.message
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Authentication / Authorization
# ---------------------------------------------------------------------------

class AuthenticationError(AIFlickError):
    """Raised when credentials are missing or invalid."""
    status_code = 401
    error_code = "authentication_required"
    message = "Valid authentication credentials are required."


class AuthorizationError(AIFlickError):
    """Raised when the authenticated user lacks permission for the resource."""
    status_code = 403
    error_code = "forbidden"
    message = "You do not have permission to perform this action."


# ---------------------------------------------------------------------------
# Tier & Quota
# ---------------------------------------------------------------------------

class TierLimitExceededError(AIFlickError):
    """Raised when a user's daily post or image quota is exhausted."""
    status_code = 429
    error_code = "quota_exceeded"
    message = "Daily generation quota reached. Your limit resets at midnight UTC."

    def __init__(
        self,
        message: Optional[str] = None,
        used: int = 0,
        limit: int = 15,
        tier: str = "free",
        resets_at: Optional[str] = None,
        resource: str = "posts",
    ):
        super().__init__(message)
        self.used = used
        self.limit = limit
        self.tier = tier
        self.resets_at = resets_at
        self.resource = resource


class TierFeatureComingSoon(AIFlickError):
    """Raised when a feature is gated behind a paid tier not yet available."""
    status_code = 503
    error_code = "feature_coming_soon"
    message = "This feature is coming soon. Stay on the Free Explorer plan for now."

    def __init__(self, message: Optional[str] = None, feature: Optional[str] = None):
        super().__init__(message)
        self.feature = feature


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

class SessionNotFoundError(AIFlickError):
    """Raised when a requested chat session does not exist."""
    status_code = 404
    error_code = "session_not_found"
    message = "Chat session not found."


class ResourceNotFoundError(AIFlickError):
    """Generic 404 for any resource that does not exist."""
    status_code = 404
    error_code = "not_found"

    def __init__(self, resource: str = "Resource", resource_id: Optional[str] = None):
        msg = f"{resource} '{resource_id}' not found." if resource_id else f"{resource} not found."
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(AIFlickError):
    """Raised for domain-level input validation failures."""
    status_code = 400
    error_code = "validation_error"
    message = "The provided input is invalid."
