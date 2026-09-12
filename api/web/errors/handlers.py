"""api/web/errors/handlers.py -- FastAPI exception handler registrations.

All HTTP-level error serialization lives here. Routes raise typed exceptions;
this module converts them to clean, consistent JSON responses. Register all
handlers via register_error_handlers(app).
"""
import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from api.web.errors.exceptions import (
    AIFlickError,
    TierLimitExceededError,
    TierFeatureComingSoon,
)

logger = logging.getLogger("aiflick.errors")


# ---------------------------------------------------------------------------
# Response Helpers
# ---------------------------------------------------------------------------

def _error_response(status_code: int, body: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Individual Handlers
# ---------------------------------------------------------------------------

async def tier_limit_handler(request: Request, exc: TierLimitExceededError) -> JSONResponse:
    """Handles daily quota exhaustion — returns 429 with quota context."""
    return _error_response(
        429,
        {
            "error": exc.error_code,
            "message": exc.message,
            "resource": exc.resource,
            "used": exc.used,
            "limit": exc.limit,
            "tier": exc.tier,
            "resets_at": exc.resets_at,
        },
    )


async def coming_soon_handler(request: Request, exc: TierFeatureComingSoon) -> JSONResponse:
    """Handles requests for features not yet available."""
    return _error_response(
        503,
        {
            "error": exc.error_code,
            "message": exc.message,
            "feature": exc.feature,
        },
    )


async def aiflick_error_handler(request: Request, exc: AIFlickError) -> JSONResponse:
    """Handles all other typed domain errors."""
    if exc.status_code >= 500:
        logger.exception("Unhandled domain error: %s", exc)
    return _error_response(
        exc.status_code,
        {
            "error": exc.error_code,
            "message": exc.message,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wraps FastAPI's built-in HTTPException in our standard error envelope."""
    detail = exc.detail
    if isinstance(detail, dict):
        return _error_response(exc.status_code, detail)
    return _error_response(
        exc.status_code,
        {
            "error": "http_error",
            "message": str(detail) if detail else "An error occurred.",
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Returns a clean 422 for request body/query validation failures."""
    errors = []
    for err in exc.errors():
        loc = " → ".join(str(p) for p in err.get("loc", []) if p != "body")
        errors.append({"field": loc or "request", "message": err.get("msg", "Invalid value")})
    return _error_response(
        422,
        {
            "error": "validation_error",
            "message": "Request validation failed.",
            "errors": errors,
        },
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handles slowapi rate limit violations — returns 429 with retry hint."""
    import time
    retry_after = 60
    try:
        current_limit = getattr(request.state, "view_rate_limit", None)
        if current_limit is not None:
            reset_at, _ = request.app.state.limiter.limiter.get_window_stats(
                current_limit[0], *current_limit[1]
            )
            retry_after = max(1, int(reset_at - time.time()))
    except Exception:
        pass
    return _error_response(
        429,
        {
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "retry_after_seconds": retry_after,
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for completely unexpected errors — logs full traceback."""
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return _error_response(
        500,
        {
            "error": "internal_error",
            "message": "An unexpected server error occurred. Please try again.",
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """Register all error handlers on the FastAPI application instance."""
    app.add_exception_handler(TierLimitExceededError, tier_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(TierFeatureComingSoon, coming_soon_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AIFlickError, aiflick_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type]
