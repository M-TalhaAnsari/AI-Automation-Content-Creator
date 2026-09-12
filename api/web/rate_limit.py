"""api/web/rate_limit.py -- Backwards-compatibility shim re-exporting from api.web.middleware.rate_limit."""
from api.web.middleware.rate_limit import (
    limiter,
    get_client_identity,
    add_rate_limit_middleware,
    TIER_RATE_LIMITS,
    DEFAULT_AUTH_LIMIT,
    DEFAULT_ANON_LIMIT,
)
from api.web.errors.handlers import rate_limit_exceeded_handler

__all__ = [
    "limiter",
    "get_client_identity",
    "add_rate_limit_middleware",
    "rate_limit_exceeded_handler",
    "TIER_RATE_LIMITS",
    "DEFAULT_AUTH_LIMIT",
    "DEFAULT_ANON_LIMIT",
]