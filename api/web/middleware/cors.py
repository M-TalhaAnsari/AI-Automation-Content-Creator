"""api/web/middleware/cors.py -- CORS configuration for AIFlick API.

Extracted from app.py so app.py stays slim and CORS rules live in one place.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _get_allowed_origins() -> list[str]:
    """Build CORS allowed origins list from environment or defaults."""
    env_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def add_cors_middleware(app: FastAPI) -> None:
    """Register CORS middleware on the FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        # Also allow any localhost:<port> for local dev flexibility
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "Content-Type",
            "Last-Event-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )
