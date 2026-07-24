"""
memory/test_redis_session_store.py

Covers the 5 cases the Phase 3 master doc requires for Split B:
1. Save then load returns an identical dict
2. Load on a nonexistent session_id returns a fresh default dict, not an error
3. Load when Redis is unreachable returns a fresh default dict, doesn't raise
4. Save when Redis is unreachable returns False, doesn't raise
5. TTL is actually set on save (checked via Redis's own TTL command)

Uses fakeredis for (1), (2), (5) -- a real in-memory Redis protocol
implementation, not a mock, so these exercise real serialize/deserialize
and real TTL behavior. Uses a raising stand-in client for (3), (4) to
simulate an actual connection failure.

Run with:  pytest memory/test_redis_session_store.py -v
"""
import copy

import fakeredis
import pytest
from redis import exceptions as redis_exceptions

from memory import redis_session_store as store


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    """Swap the module's real Redis client for a fakeredis instance,
    fresh for every test."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store, "_client", fake)
    yield fake


class _AlwaysDownClient:
    """Stands in for a Redis client that can't reach the server --
    every call raises the same error redis-py raises on a real timeout/
    connection-refused."""
    def get(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def set(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def delete(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def ping(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")


def test_save_then_load_roundtrip():
    session_id = "sess-roundtrip"
    conversation = copy.deepcopy(store._DEFAULT_CONVERSATION)
    conversation["last_topic"] = "ai automation tools"
    conversation["last_platform"] = "linkedin"
    conversation["active_constraints"] = [{"type": "exclude", "value": "n8n"}]
    conversation["message_history"] = [{"role": "user", "content": "hi"}]
    conversation["gate_tokens_used"] = 42

    ok = store.save_conversation(session_id, conversation)
    assert ok is True

    loaded = store.load_conversation(session_id)
    assert loaded == conversation


def test_load_nonexistent_session_returns_fresh_default():
    loaded = store.load_conversation("sess-never-existed")
    assert loaded == store._DEFAULT_CONVERSATION
    # Must be a copy, not the same object, or a caller mutating it would
    # corrupt every future "fresh default".
    assert loaded is not store._DEFAULT_CONVERSATION


def test_load_when_redis_unreachable_returns_fresh_default(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    loaded = store.load_conversation("sess-doesnt-matter")
    assert loaded == store._DEFAULT_CONVERSATION


def test_save_when_redis_unreachable_returns_false(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    ok = store.save_conversation("sess-doesnt-matter", copy.deepcopy(store._DEFAULT_CONVERSATION))
    assert ok is False


def test_ttl_is_set_on_save(fake_client):
    session_id = "sess-ttl-check"
    store.save_conversation(session_id, copy.deepcopy(store._DEFAULT_CONVERSATION))

    ttl = fake_client.ttl(store._key(session_id))
    assert ttl > 0
    assert ttl <= store.SESSION_TTL_SECONDS


def test_corrupted_entry_returns_fresh_default_not_a_crash(fake_client):
    session_id = "sess-corrupted"
    fake_client.set(store._key(session_id), "{not valid json::")
    loaded = store.load_conversation(session_id)
    assert loaded == store._DEFAULT_CONVERSATION


def test_delete_conversation_removes_key(fake_client):
    session_id = "sess-to-delete"
    store.save_conversation(session_id, copy.deepcopy(store._DEFAULT_CONVERSATION))
    assert fake_client.get(store._key(session_id)) is not None

    ok = store.delete_conversation(session_id)
    assert ok is True
    assert fake_client.get(store._key(session_id)) is None


def test_delete_when_redis_unreachable_returns_false(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    ok = store.delete_conversation("sess-doesnt-matter")
    assert ok is False


def test_missing_new_field_merges_over_default(fake_client):
    """Simulates an old session saved before a new field (e.g.
    gate_tokens_used) existed -- load must fill it in from the default
    instead of leaving it out."""
    session_id = "sess-old-schema"
    old_shape = {"last_topic": "old topic", "last_platform": "instagram"}
    fake_client.set(store._key(session_id), __import__("json").dumps(old_shape))

    loaded = store.load_conversation(session_id)
    assert loaded["last_topic"] == "old topic"
    assert loaded["gate_tokens_used"] == 0  # backfilled from default
    assert loaded["message_history"] == []  # backfilled from default