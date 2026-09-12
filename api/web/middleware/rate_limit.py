"""api/web/middleware/rate_limit.py -- Per-identity request rate limiting via slowapi.

Each request is keyed to its AIFlick identity (user:{id} for authenticated users,
anon:{id} for guests) so rate limits are per-person, not per-IP.

Tier-aware limits are applied via the @limiter.limit() decorator on route handlers.
The TIER_LIMITS map provides the strings to use per tier.
"""
import os

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware

from api.web.services.auth_service import JWT_SECRET, JWT_ALGORITHM

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Tier-aware rate limit strings
# ---------------------------------------------------------------------------
# These are used as decorators: @limiter.limit(TIER_LIMITS["free"])
# For now creator/agency are not purchasable, so we expose the same limits
# as free but define higher caps ready for when billing goes live.

TIER_RATE_LIMITS: dict[str, str] = {
    "anon":    "5/minute",
    "free":    "20/minute",
    "creator": "20/minute",   # Will become 60/minute when billing is live
    "agency":  "20/minute",   # Will become 120/minute when billing is live
}

# Default limit used on @limiter.limit() decorator — authenticated users
DEFAULT_AUTH_LIMIT = TIER_RATE_LIMITS["free"]
DEFAULT_ANON_LIMIT = TIER_RATE_LIMITS["anon"]


# ---------------------------------------------------------------------------
# Identity key function
# ---------------------------------------------------------------------------

def get_client_identity(request: Request) -> str:
    """
    Extracts the per-person identity for rate-limit keying.
    Priority: Bearer JWT sub → X-Anon-Id header → 'unauthenticated' bucket.
    """
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer ") and JWT_SECRET:
        import jwt
        token = authorization[len("Bearer "):]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return str(payload.get("sub", "unauthenticated"))
        except jwt.PyJWTError:
            pass

    anon_id = request.headers.get("X-Anon-Id")
    if anon_id:
        return f"anon:{anon_id}"

    return "unauthenticated"


# ---------------------------------------------------------------------------
# Limiter instance (shared across all routes)
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=get_client_identity,
    storage_uri=REDIS_URL,
    headers_enabled=True,  # Sends X-RateLimit-* headers in responses
)


def add_rate_limit_middleware(app: FastAPI) -> None:
    """Attach the slowapi limiter state and middleware to the FastAPI app."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
