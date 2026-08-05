"""web/rate_limit.py -- per-identity rate limiting via slowapi.

Fixed (Phase 8): this previously keyed on X-API-Key, a header nothing has
sent since Phase 7 switched /chat etc. to JWT auth -- every request was
silently collapsing into the shared "unauthenticated" bucket regardless of
who was actually calling. Now reads the same identity Depends(verify_jwt)/
Depends(verify_identity) resolve, via one shared header-parsing helper --
not a second, independently-drifting comparison, same principle as
resolve_client_name's reuse in the old API-key path.
"""
import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from api.web.auth import JWT_ALGORITHM, JWT_SECRET

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def get_client_identity(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer ") and JWT_SECRET:
        import jwt
        token = authorization[len("Bearer "):]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload["sub"]
        except jwt.PyJWTError:
            pass

    anon_id = request.headers.get("X-Anon-Id")
    if anon_id:
        return f"anon:{anon_id}"

    return "unauthenticated"


limiter = Limiter(
    key_func=get_client_identity,
    storage_uri=REDIS_URL,
    headers_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
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