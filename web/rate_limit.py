"""
web/rate_limit.py -- per-client rate limiting via slowapi (Phase 5).

Locked design decisions (Phase 5 master doc, section 2):
- Scoped by client_name (from the API key), not by IP. IP-based
  limiting would misattribute e.g. an entire Slack workspace's traffic
  behind one shared proxy IP to a single bucket, and doesn't match how
  this project already tracks identity (Phase 4's whole point).
- Reuses web.auth's resolve_client_name() rather than a second,
  parallel key-comparison implementation. slowapi's key_func receives
  the raw Request, not FastAPI's already-resolved Depends(verify_api_key)
  value -- those are resolved independently by FastAPI's dependency
  system, and slowapi's decorator has no access to sibling dependency
  results -- so it must read the X-API-Key header itself, but through
  the exact same lookup verify_api_key uses.
- Backed by Redis (same REDIS_URL as everything else in this project),
  not in-memory, so limits are correctly shared the moment this ever
  runs as more than one app replica. Multi-replica scaling itself is
  out of scope for this phase, but an in-memory limiter would silently
  stop working correctly the day that changes -- not worth painting
  into that corner now.
"""
import os
import time
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from web.auth import resolve_client_name

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def get_client_identity(request: Request) -> str:
    """
    Rate-limit key function. Returns the client_name for the API key on
    this request, resolved the exact same way verify_api_key resolves
    it -- just read independently from the raw header, since slowapi's
    key_func can't access FastAPI's already-resolved dependency values.

    CRITICAL: any request with a missing or unregistered key collapses
    into the SAME shared bucket ("unauthenticated") -- it must NEVER
    fall back to the raw key value itself. Confirmed by direct testing:
    using the raw (invalid) key as the identity means every different
    garbage key gets its own fresh, never-before-seen bucket, so an
    attacker rotating the key on every single request faces no
    practical rate limit at all (30 requests, 30 different garbage
    keys, zero got throttled). Collapsing to one shared bucket means
    the AGGREGATE volume of all failed-auth traffic combined is capped
    at the route's normal limit (e.g. 10/minute total across every
    invalid key someone tries), before FastAPI's own dependency
    resolution (Depends(verify_api_key)) ever runs -- SlowAPIMiddleware
    is genuine ASGI middleware that checks limits ahead of routing/
    dependency injection, confirmed by reading slowapi's own installed
    source, not assumed.
    """
    api_key = request.headers.get("X-API-Key")
    client_name = resolve_client_name(api_key)
    if client_name:
        return client_name
    return "unauthenticated"


limiter = Limiter(
    key_func=get_client_identity,
    storage_uri=REDIS_URL,
    headers_enabled=True,  # adds X-RateLimit-* / Retry-After response headers, standard practice
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom 429 handler matching this project's response-shape contract:
    {"error": "rate_limit_exceeded", "retry_after_seconds": <int>}

    retry_after_seconds is computed from the SAME window-stats query
    slowapi's own built-in header injection uses internally (confirmed
    by reading slowapi's actual installed source, not assumed from
    docs) -- not a hardcoded or guessed number. Falls back to a
    conservative 60s only if that computation itself fails for some
    reason (e.g. Redis hiccup mid-response) -- the failure mode is a
    slightly-wrong retry hint, never a crashed response.
    """
    retry_after_seconds = 60
    try:
        current_limit = getattr(request.state, "view_rate_limit", None)
        if current_limit is not None:
            reset_at, _remaining = request.app.state.limiter.limiter.get_window_stats(
                current_limit[0], *current_limit[1]
            )
            retry_after_seconds = max(1, int(reset_at - time.time()))
    except Exception:
        pass

    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "retry_after_seconds": retry_after_seconds},
    )