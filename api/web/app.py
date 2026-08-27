"""api/web/app.py -- FastAPI application entrypoint with modular routing and dependencies."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from memory.redis_session_store import ping as redis_ping
from api.web.db import init_db
from api.web.dependencies.rate_limit_deps import limiter, rate_limit_exceeded_handler
from api.web.routes.auth_routes import router as auth_router
from api.web.routes.chat_routes import router as chat_router
from api.web.routes.session_routes import router as session_router
from api.web.image_routes import router as image_router

logger = logging.getLogger("trendforge.web.app")

app = FastAPI(
    title="TrendForge Social Content & Visual Studio API",
    description="Production-grade API for generating viral social posts and high-converting graphics",
    version="2.0.0",
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("init_db() failed at startup: %s", e)


@app.get("/health")
def health():
    return {"ok": True, "redis": redis_ping()}


# Register modular routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(image_router)
