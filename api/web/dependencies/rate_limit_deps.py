"""api/web/dependencies/rate_limit_deps.py -- Rate limiting dependencies."""
from api.web.middleware.rate_limit import limiter
from api.web.errors.handlers import rate_limit_exceeded_handler

__all__ = ["limiter", "rate_limit_exceeded_handler"]
