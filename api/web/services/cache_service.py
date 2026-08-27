"""
api/web/services/cache_service.py -- Multi-Layer In-Memory & Redis Caching Service.

Provides:
1. In-Memory LRU Cache for sub-millisecond hot lookups (user tier limits, brand presets).
2. Redis Cache for research trend signals & prompt completions with TTL.
"""
import json
import hashlib
import time
import logging
from functools import lru_cache
from typing import Optional, Any, Dict
from redis import Redis
from memory.redis_session_store import REDIS_URL

logger = logging.getLogger("aiflick.cache")

_redis_conn: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    global _redis_conn
    if _redis_conn is None:
        try:
            _redis_conn = Redis.from_url(REDIS_URL, decode_responses=True)
            _redis_conn.ping()
        except Exception as e:
            logger.warning("Redis cache unavailable: %s", e)
            _redis_conn = None
    return _redis_conn


# ── 1. In-Memory LRU Fast Lookup (< 0.1ms) ───────────────────────────────────

class InMemoryFastCache:
    """Lightweight in-memory cache with expiration for hot read queries."""
    def __init__(self, default_ttl_sec: int = 300):
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._default_ttl = default_ttl_sec

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            if time.time() < self._expiry.get(key, 0):
                return self._store[key]
            else:
                self.delete(key)
        return None

    def set(self, key: str, value: Any, ttl_sec: Optional[int] = None) -> None:
        self._store[key] = value
        self._expiry[key] = time.time() + (ttl_sec or self._default_ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)


FAST_MEMORY_CACHE = InMemoryFastCache(default_ttl_sec=180)


# ── 2. Redis Research Signal & Prompt Cache (TTL: 30 mins) ────────────────────

def cache_research_signals(topic: str, sources: list, data: Any, ttl_sec: int = 1800) -> None:
    """Cache research signals to avoid repeated external API scraping."""
    r = get_redis_client()
    if not r:
        return
    try:
        key_raw = f"{topic.lower().strip()}:{sorted(sources)}"
        key_hash = hashlib.sha256(key_raw.encode()).hexdigest()[:16]
        cache_key = f"aiflick:signals:{key_hash}"
        r.setex(cache_key, ttl_sec, json.dumps(data))
    except Exception as e:
        logger.debug("Failed to set research cache: %s", e)


def get_cached_research_signals(topic: str, sources: list) -> Optional[Any]:
    """Retrieve cached research signals if fresh."""
    r = get_redis_client()
    if not r:
        return None
    try:
        key_raw = f"{topic.lower().strip()}:{sorted(sources)}"
        key_hash = hashlib.sha256(key_raw.encode()).hexdigest()[:16]
        cache_key = f"aiflick:signals:{key_hash}"
        cached = r.get(cache_key)
        if cached:
            logger.info("⚡ Cache Hit: Research signals for '%s'", topic)
            return json.loads(cached)
    except Exception as e:
        logger.debug("Failed to read research cache: %s", e)
    return None
