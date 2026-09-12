"""api/web/errors/ -- Centralized exception classes and FastAPI error handlers."""
from api.web.errors.exceptions import (
    AIFlickError,
    AuthenticationError,
    AuthorizationError,
    TierLimitExceededError,
    TierFeatureComingSoon,
    SessionNotFoundError,
    ResourceNotFoundError,
    ValidationError,
)

__all__ = [
    "AIFlickError",
    "AuthenticationError",
    "AuthorizationError",
    "TierLimitExceededError",
    "TierFeatureComingSoon",
    "SessionNotFoundError",
    "ResourceNotFoundError",
    "ValidationError",
]
