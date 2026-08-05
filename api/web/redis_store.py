"""
web/redis_store.py -- live conversation state, backed by Redis.

This is deliberately separate from memory/session_store.py: that module is
your permanent, unbounded history (every session, forever, queried by
--history and get_already_covered()). This module is the opposite: one
conversation dict per active session_id, expected to be small, expected to
expire, and read/written on almost every request.

Key shape:  session:{session_id}  ->  JSON string of the conversation dict
TTL:        refreshed on every save, so an active conversation never expires
            mid-use, but an abandoned one cleans itself up automatically.
"""
import json
import os
from typing import Any, Dict, Optional

import api.web.redis_store as redis_store

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 60 * 60 * 48))  # 48h default
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_DEFAULT_CONVERSATION: Dict[str, Any] = {
    "last_topic": None,
    "last_platform": None,
    "last_content_intent": None,
    "last_generated_posts": [],
    "last_output": None,
    "active_constraints": [],
    "leftover_fetch_pool": [],
    "recent_messages": [],
}


def _client() -> "redis_store.Redis":
    # decode_responses=True so callers get str, not bytes, out of Redis.
    return redis_store.Redis.from_url(REDIS_URL, decode_responses=True)


def _key(session_id: str) -> str:
    return f"session:{session_id}"


def get_conversation(session_id: str) -> Dict[str, Any]:
    """Loads the conversation dict for a session, or a fresh default if
    none exists yet (new session, or the old one expired)."""
    raw = _client().get(_key(session_id))
    if raw is None:
        return dict(_DEFAULT_CONVERSATION)
    try:
        data = json.loads(raw)
        # Merge over defaults so a schema change (e.g. a new field added
        # later) doesn't break existing sessions -- missing keys just get
        # the default instead of a KeyError downstream.
        merged = dict(_DEFAULT_CONVERSATION)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, TypeError):
        # Corrupted entry -- fail safe to a fresh conversation rather than
        # 500ing the request. Worth logging in a real deployment.
        return dict(_DEFAULT_CONVERSATION)


def save_conversation(session_id: str, conversation: Dict[str, Any]) -> None:
    """Persists the conversation dict and refreshes its TTL. Called after
    every turn, whether handled inline or by a background job."""
    _client().set(_key(session_id), json.dumps(conversation), ex=SESSION_TTL_SECONDS)


def delete_conversation(session_id: str) -> None:
    _client().delete(_key(session_id))


def ping() -> bool:
    """Health-check helper for a /health endpoint."""
    try:
        return _client().ping()
    except redis_store.exceptions.RedisError:
        return False