"""
memory/redis_session_store.py -- live, per-session conversation state,
backed by Redis.

Deliberately separate from memory/session_store.py: that module is the
permanent, unbounded, cross-session history (queried by --history and
get_already_covered()). This module is the opposite -- one small
conversation dict per active session_id, expected to expire, read/written
on almost every turn.

Key shape:  tf:session:{client_name}:{session_id}  ->  JSON string of the conversation dict
TTL:        refreshed on every save (sliding expiry) so an active
            conversation never expires mid-use, but an abandoned one
            cleans itself up on its own.

Client scoping (Phase 4): every session is namespaced by the client
that created it (see verify_api_key in web/auth.py for where
client_name comes from). A different client requesting the same
session_id string gets a fresh empty session, not an error and not a
peek at someone else's data -- this falls directly out of the key
shape above, not a separate permission check.

Contract (must match main.py's interactive_mode() initializer exactly --
see Phase 3 master doc, section 1):
    last_topic, last_platform, last_content_intent, last_generated_posts,
    last_output, active_constraints, leftover_fetch_pool, message_history,
    rolling_summary, gate_tokens_used
"""
import copy
import json
import logging
import os
from typing import Any, Dict

import redis
from redis import exceptions as redis_exceptions

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 60 * 60 * 24))  # 24h, per master doc
KEY_PREFIX = "tf:session:"

# Exact match to main.py's interactive_mode() initializer. If that
# initializer changes, this must change with it -- these two are meant
# to drift together, not independently.
_DEFAULT_CONVERSATION: Dict[str, Any] = {
    "last_topic": None,
    "last_platform": None,
    "last_content_intent": None,
    "last_generated_posts": [],
    "last_output": None,
    "active_constraints": [],
    "leftover_fetch_pool": [],
    "message_history": [],
    "rolling_summary": "",
    "gate_tokens_used": 0,
}

# One client for the whole process -- redis-py pools connections
# internally, so there's no benefit to constructing a fresh client per
# call, only overhead. decode_responses=True so callers get str, not
# bytes, out of Redis.
_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_redis_client() -> redis.Redis:
    """Single connection point. Exposed mainly so tests can monkeypatch
    it, and so other modules never have to construct their own client."""
    return _client


def _key(session_id: str, client_name: str) -> str:
    return f"{KEY_PREFIX}{client_name}:{session_id}"


def _fresh_default() -> Dict[str, Any]:
    # Deep copy -- the module-level dict above must never be handed out
    # by reference, or one session's mutations would leak into another's
    # "default" the next time this function is called.
    return copy.deepcopy(_DEFAULT_CONVERSATION)


def load_conversation(session_id: str, client_name: str) -> Dict[str, Any]:
    """
    Returns the conversation dict for this (client_name, session_id)
    pair, or a fresh default dict if none exists yet, the entry is
    corrupted, or Redis is unreachable.

    Client scoping is entirely a property of the Redis key shape
    (f"{KEY_PREFIX}{client_name}:{session_id}") -- there is no separate
    "check ownership" step. If session_id "abc" was created by client
    "web", it lives under a completely different key than what client
    "slack" would look up for the same session_id string. A different
    client asking for the same session_id therefore just misses,
    identically to how a brand-new session_id misses -- the two cases
    are indistinguishable by construction, which is the point (never
    leak that a session_id exists under someone else's ownership).

    Never raises. Redis being down degrades the request (user loses
    conversation memory for that turn) rather than failing it.
    """
    try:
        raw = _client.get(_key(session_id, client_name))
    except redis_exceptions.RedisError as e:
        logger.warning("redis_session_store.load_conversation: Redis unreachable for %s/%s: %s", client_name, session_id, e)
        return _fresh_default()

    if raw is None:
        return _fresh_default()

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("stored session was not a JSON object")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("redis_session_store.load_conversation: corrupted entry for %s/%s: %s", client_name, session_id, e)
        return _fresh_default()

    # Merge over defaults so a schema change (new field added later, e.g.
    # gate_tokens_used didn't always exist) doesn't KeyError downstream --
    # missing keys get the default instead.
    merged = _fresh_default()
    merged.update(data)
    return merged


def save_conversation(session_id: str, client_name: str, conversation: Dict[str, Any]) -> bool:
    """
    Serializes and saves conversation, refreshing its TTL. Returns True
    on success, False on failure. Never raises -- a failed save is
    logged, not fatal to a request that already computed a valid
    response.
    """
    try:
        payload = json.dumps(conversation)
    except (TypeError, ValueError) as e:
        # Something non-JSON-safe snuck into the dict. Per the master
        # doc: don't silently pickle around it, surface it loudly instead
        # so the actual offending field gets found and fixed.
        logger.error("redis_session_store.save_conversation: non-JSON-safe conversation for %s/%s: %s", client_name, session_id, e)
        return False

    try:
        _client.set(_key(session_id, client_name), payload, ex=SESSION_TTL_SECONDS)
        return True
    except redis_exceptions.RedisError as e:
        logger.warning("redis_session_store.save_conversation: Redis unreachable for %s/%s: %s", client_name, session_id, e)
        return False


def delete_conversation(session_id: str, client_name: str) -> bool:
    """
    For the DELETE /session/{id} endpoint. Never raises.

    A delete request for a session_id owned by a different client is a
    no-op that still returns True: Redis's DELETE command is a no-op
    (returns 0 keys deleted) when the key doesn't exist under this
    client's namespace, and that's exactly what "not yours" looks like
    here -- there's no separate check needed, and no error that would
    reveal an ownership mismatch to the caller.
    """
    try:
        _client.delete(_key(session_id, client_name))
        return True
    except redis_exceptions.RedisError as e:
        logger.warning("redis_session_store.delete_conversation: Redis unreachable for %s/%s: %s", client_name, session_id, e)
        return False


def ping() -> bool:
    """Health-check helper for a /health endpoint. Never raises."""
    try:
        return bool(_client.ping())
    except redis_exceptions.RedisError:
        return False