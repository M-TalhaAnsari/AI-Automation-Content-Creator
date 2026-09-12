"""api/web/app.py -- FastAPI application entrypoint with modular architecture.

Wiring:
- CORS middleware: api.web.middleware.cors
- Rate limiting middleware: api.web.middleware.rate_limit
- Centralized exception handlers: api.web.errors.handlers
- Modular route controllers: api.web.routes.*
"""
import logging
from fastapi import FastAPI

from memory.redis_session_store import ping as redis_ping
from api.web.db import init_db
from api.web.middleware.cors import add_cors_middleware
from api.web.middleware.rate_limit import add_rate_limit_middleware
from api.web.errors.handlers import register_error_handlers

from api.web.routes.auth_routes import router as auth_router
from api.web.routes.chat_routes import router as chat_router
from api.web.routes.session_routes import router as session_router
from api.web.routes.preferences_routes import router as preferences_router
from api.web.image_routes import router as image_router

logger = logging.getLogger("aiflick.app")

app = FastAPI(
    title="AIFlick Social Content & Visual Studio API",
    description="Production-grade API for generating viral social posts and high-converting graphics",
    version="2.0.0",
)

# 1. Register middleware layers
add_cors_middleware(app)
add_rate_limit_middleware(app)

# 2. Register centralized error handlers
register_error_handlers(app)


# 3. Database initialization on startup
@app.on_event("startup")
def _startup():
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("init_db() failed at startup: %s", e)


# 4. System Health Check
@app.get("/health")
def health():
    return {"ok": True, "redis": redis_ping()}


# 5. Register modular route controllers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(preferences_router)
app.include_router(image_router)
