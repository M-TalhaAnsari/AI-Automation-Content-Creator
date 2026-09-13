"""memory/redis_session_store.py -- live conversation state, Redis as a fast
cache in front of Postgres (web/db.py), which is the permanent store."""
import copy
import json
import logging
import os
from typing import Any, Dict

import redis
from redis import exceptions as redis_exceptions

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 60 * 60 * 24))
KEY_PREFIX = "tf:session:"

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
    "post_history": [],
    "pending_confirmation": None,
}

_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_redis_client() -> redis.Redis:
    return _client


def _key(session_id: str, client_name: str) -> str:
    return f"{KEY_PREFIX}{client_name}:{session_id}"


def _fresh_default() -> Dict[str, Any]:
    return copy.deepcopy(_DEFAULT_CONVERSATION)


def _merged(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = _fresh_default()
    merged.update(data)
    return merged


def load_conversation(session_id: str, client_name: str) -> Dict[str, Any]:
    try:
        raw = _client.get(_key(session_id, client_name))
    except redis_exceptions.RedisError as e:
        logger.warning("Redis unreachable on load for %s/%s: %s", client_name, session_id, e)
        raw = None

    if raw is not None:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return _merged(data)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Corrupted Redis entry for %s/%s: %s", client_name, session_id, e)

    # Redis miss (expired, evicted, or never cached) -- fall back to Postgres,
    # which is the actual permanent store.
    try:
        from api.web.db import load_conversation_from_db, parse_user_id
        user_id = parse_user_id(client_name)
        db_data = load_conversation_from_db(user_id, session_id)
    except Exception as e:
        logger.info("No Postgres fallback for %s/%s: %s", client_name, session_id, e)
        db_data = None

    if db_data is None:
        return _fresh_default()

    merged = _merged(db_data)
    try:
        _client.set(_key(session_id, client_name), json.dumps(merged), ex=SESSION_TTL_SECONDS)
    except redis_exceptions.RedisError:
        pass
    return merged


def save_conversation(session_id: str, client_name: str, conversation: Dict[str, Any]) -> bool:
    try:
        payload = json.dumps(conversation)
    except (TypeError, ValueError) as e:
        logger.error("Non-JSON-safe conversation for %s/%s: %s", client_name, session_id, e)
        return False

    redis_ok = True
    try:
        _client.set(_key(session_id, client_name), payload, ex=SESSION_TTL_SECONDS)
    except redis_exceptions.RedisError as e:
        logger.warning("Redis unreachable on save for %s/%s: %s", client_name, session_id, e)
        redis_ok = False

    try:
        from api.web.db import save_conversation_to_db, parse_user_id
        user_id = parse_user_id(client_name)
        save_conversation_to_db(user_id, session_id, conversation)
    except Exception as e:
        logger.info("No Postgres write for %s/%s: %s", client_name, session_id, e)

    return redis_ok


def delete_conversation(session_id: str, client_name: str) -> bool:
    try:
        _client.delete(_key(session_id, client_name))
        return True
    except redis_exceptions.RedisError as e:
        logger.warning("Redis unreachable on delete for %s/%s: %s", client_name, session_id, e)
        return False


def claim_guest_conversation(guest_session_id: str, target_client_name: str) -> bool:
    """Find any conversation stored with guest_session_id under an IP/guest key,
    and copy/persist it under target_client_name (e.g. 'user:4').
    Also ensures the session is inserted into Postgres chat_sessions.
    """
    try:
        keys = _client.keys(f"{KEY_PREFIX}*:{guest_session_id}")
    except redis_exceptions.RedisError as e:
        logger.warning("Redis keys search failed for guest session %s: %s", guest_session_id, e)
        keys = []

    target_key = _key(guest_session_id, target_client_name)
    conversation = None

    for k in keys:
        if k != target_key:
            try:
                raw = _client.get(k)
                if raw:
                    conversation = json.loads(raw)
                    break
            except Exception:
                continue

    if not conversation:
        return False

    # Save under target authenticated client name (persists to Redis & Postgres)
    save_conversation(guest_session_id, target_client_name, conversation)

    try:
        from api.web.db import upsert_chat_session, parse_user_id
        user_id = parse_user_id(target_client_name)
        title = conversation.get("last_topic") or "Imported session"
        upsert_chat_session(user_id, guest_session_id, title)
    except Exception as e:
        logger.info("Could not upsert chat session in Postgres for %s: %s", guest_session_id, e)

    return True


def ping() -> bool:
    try:
        return bool(_client.ping())
    except redis_exceptions.RedisError:
        return False