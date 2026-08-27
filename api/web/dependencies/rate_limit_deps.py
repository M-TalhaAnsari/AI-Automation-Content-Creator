"""api/web/dependencies/rate_limit_deps.py -- Rate limiting dependencies."""
from api.web.rate_limit import limiter, rate_limit_exceeded_handler

__all__ = ["limiter", "rate_limit_exceeded_handler"]
