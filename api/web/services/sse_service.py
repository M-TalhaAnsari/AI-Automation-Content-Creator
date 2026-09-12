"""api/web/services/sse_service.py -- Production-grade Server-Sent Events (SSE) service
backed by Redis Streams with Last-Event-ID reconnection support and ticket auth.
"""
import json
import logging
import os
import secrets
import time
from typing import Any, AsyncGenerator, Dict, Optional

from redis import exceptions as redis_exceptions

from memory.redis_session_store import get_redis_client

logger = logging.getLogger("aiflick.sse")

STREAM_PREFIX = "tf:stream:"
TICKET_PREFIX = "tf:sse_ticket:"
TICKET_TTL_SECONDS = 60  # Ticket expires in 60s
STREAM_TTL_SECONDS = 3600  # Stream kept in Redis for 1 hour for reconnects


def create_sse_ticket(client_name: str, stream_key: str) -> str:
    """
    Generates a secure single-use ticket for authenticating SSE EventSource/fetch connections
    without exposing long-lived JWTs in URL query parameters.
    """
    ticket = secrets.token_urlsafe(32)
    client = get_redis_client()
    payload = json.dumps({
        "client_name": client_name,
        "stream_key": stream_key,
        "created_at": time.time(),
    })
    try:
        client.set(f"{TICKET_PREFIX}{ticket}", payload, ex=TICKET_TTL_SECONDS)
    except redis_exceptions.RedisError as e:
        logger.error("Failed to store SSE ticket: %s", e)
    return ticket


def verify_sse_ticket(ticket: str, expected_stream_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Validates and consumes single-use ticket. Returns payload dict or None.
    """
    if not ticket:
        return None
    client = get_redis_client()
    key = f"{TICKET_PREFIX}{ticket}"
    try:
        raw = client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        if expected_stream_key and data.get("stream_key") != expected_stream_key:
            return None
        # Consume ticket on use
        client.delete(key)
        return data
    except (redis_exceptions.RedisError, json.JSONDecodeError) as e:
        logger.warning("Error verifying SSE ticket: %s", e)
        return None


def format_sse_message(event_id: str, event_type: str, data: Any) -> str:
    """Formats an event into standard SSE wire specification."""
    data_str = json.dumps(data) if not isinstance(data, str) else data
    return f"id: {event_id}\nevent: {event_type}\ndata: {data_str}\n\n"


def format_sse_heartbeat() -> str:
    """SSE comment line heartbeat to keep connections alive across reverse proxies."""
    return f": heartbeat {int(time.time())}\n\n"


def publish_sse_event(stream_key: str, event_type: str, data: Any) -> Optional[str]:
    """
    Publishes an event to a Redis Stream with capped memory (maxlen=200).
    Returns the Redis Stream ID (e.g. '1726154823901-0') or None.
    """
    client = get_redis_client()
    redis_key = f"{STREAM_PREFIX}{stream_key}"
    serialized_data = json.dumps(data) if not isinstance(data, str) else data

    try:
        # XADD key MAXLEN ~ 200 * field value
        entry_id = client.xadd(
            redis_key,
            {"event": event_type, "data": serialized_data},
            maxlen=200,
            approximate=True,
        )
        # Ensure stream expires after 1 hour so it does not leak memory
        client.expire(redis_key, STREAM_TTL_SECONDS)
        if isinstance(entry_id, bytes):
            return entry_id.decode("utf-8")
        return str(entry_id) if entry_id else None
    except redis_exceptions.RedisError as e:
        logger.error("Failed to publish SSE event to %s: %s", redis_key, e)
        return None


def read_stream_events_batch(stream_key: str, last_id: str = "0-0", count: int = 50, block_ms: int = 5000):
    """
    Reads a batch of events from Redis Stream starting strictly after last_id.
    Uses XREAD with BLOCK.
    """
    client = get_redis_client()
    redis_key = f"{STREAM_PREFIX}{stream_key}"
    effective_last_id = last_id if (last_id and last_id.strip()) else "0-0"

    try:
        results = client.xread({redis_key: effective_last_id}, count=count, block=block_ms)
        if not results:
            return []
        # results format: [[stream_name, [[entry_id, {field: val}], ...]]]
        events = []
        for stream_name, entries in results:
            for entry_id, fields in entries:
                eid = entry_id.decode("utf-8") if isinstance(entry_id, bytes) else str(entry_id)
                raw_event = fields.get("event") or fields.get(b"event") or "message"
                event_type = raw_event.decode("utf-8") if isinstance(raw_event, bytes) else str(raw_event)
                raw_data = fields.get("data") or fields.get(b"data") or "{}"
                event_data = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                events.append((eid, event_type, event_data))
        return events
    except redis_exceptions.RedisError as e:
        logger.error("Error reading stream %s: %s", redis_key, e)
        return []
