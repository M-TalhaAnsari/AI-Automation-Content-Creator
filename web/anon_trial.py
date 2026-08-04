"""web/anon_trial.py -- usage tracking for pre-login guest chat (Phase 8).

Anonymous conversations are Redis-only by design (see redis_session_store's
Postgres fallback -- parse_user_id() rejects any client_name not shaped
"user:{id}", so an "anon:{id}" identity never touches Postgres). This module
tracks message/token usage per anon id the same way, so the guest experience
never creates a durable account trace before the person actually signs up.
"""
import json
import os

import redis
from redis import exceptions as redis_exceptions

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MAX_ANON_MESSAGES = int(os.environ.get("MAX_ANON_MESSAGES", 3))
MAX_ANON_TOKENS = int(os.environ.get("MAX_ANON_TOKENS", 3000))
TTL_SECONDS = 60 * 60 * 24

_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _key(anon_id: str) -> str:
    return f"tf:anon_trial:{anon_id}"


def get_usage(anon_id: str) -> dict:
    try:
        raw = _client.get(_key(anon_id))
    except redis_exceptions.RedisError:
        return {"message_count": 0, "tokens_used": 0}
    if not raw:
        return {"message_count": 0, "tokens_used": 0}
    try:
        data = json.loads(raw)
        return {"message_count": data.get("message_count", 0), "tokens_used": data.get("tokens_used", 0)}
    except (json.JSONDecodeError, TypeError):
        return {"message_count": 0, "tokens_used": 0}


def is_over_limit(anon_id: str) -> bool:
    usage = get_usage(anon_id)
    return usage["message_count"] >= MAX_ANON_MESSAGES or usage["tokens_used"] >= MAX_ANON_TOKENS


def record_message(anon_id: str, tokens_used: int = 0) -> None:
    usage = get_usage(anon_id)
    usage["message_count"] += 1
    usage["tokens_used"] += max(0, tokens_used)
    try:
        _client.set(_key(anon_id), json.dumps(usage), ex=TTL_SECONDS)
    except redis_exceptions.RedisError:
        pass


def add_tokens(anon_id: str, tokens_used: int) -> None:
    if tokens_used <= 0:
        return
    usage = get_usage(anon_id)
    usage["tokens_used"] += tokens_used
    try:
        _client.set(_key(anon_id), json.dumps(usage), ex=TTL_SECONDS)
    except redis_exceptions.RedisError:
        pass