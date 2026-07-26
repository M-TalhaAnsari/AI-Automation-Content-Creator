"""
memory/test_redis_session_store.py

Phase 3's original 9 tests, updated to pass client_name (the store's
signatures changed in Phase 4 -- every call now takes it), plus the 3
new scoping tests the Phase 4 master doc requires:
  1. Client A saves, Client B loads the SAME session_id -> fresh default,
     not Client A's data
  2. Client A saves, Client A loads -> gets its own data back correctly
     (regression check that scoping didn't break the normal case)
  3. Client B deletes a session_id that exists but belongs to Client A ->
     returns True, but Client A's session is unchanged afterward

Uses fakeredis for all of these -- real Redis wire-protocol behavior,
not a mock.

Run with:  pytest memory/test_redis_session_store.py -v
"""
import copy
import json

import fakeredis
import pytest
from redis import exceptions as redis_exceptions

from memory import redis_session_store as store

CLIENT_A = "web"
CLIENT_B = "slack"


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store, "_client", fake)
    yield fake


class _AlwaysDownClient:
    def get(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def set(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def delete(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")

    def ping(self, *a, **k):
        raise redis_exceptions.ConnectionError("simulated: connection refused")


# --- Phase 3 regression tests, updated for client_name -----------------

def test_save_then_load_roundtrip():
    session_id = "sess-roundtrip"
    conversation = copy.deepcopy(store._DEFAULT_CONVERSATION)
    conversation["last_topic"] = "ai automation tools"
    conversation["last_platform"] = "linkedin"
    conversation["active_constraints"] = [{"type": "exclude", "value": "n8n"}]
    conversation["message_history"] = [{"role": "user", "content": "hi"}]
    conversation["gate_tokens_used"] = 42

    ok = store.save_conversation(session_id, CLIENT_A, conversation)
    assert ok is True

    loaded = store.load_conversation(session_id, CLIENT_A)
    assert loaded == conversation


def test_load_nonexistent_session_returns_fresh_default():
    loaded = store.load_conversation("sess-never-existed", CLIENT_A)
    assert loaded == store._DEFAULT_CONVERSATION
    assert loaded is not store._DEFAULT_CONVERSATION


def test_load_when_redis_unreachable_returns_fresh_default(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    loaded = store.load_conversation("sess-doesnt-matter", CLIENT_A)
    assert loaded == store._DEFAULT_CONVERSATION


def test_save_when_redis_unreachable_returns_false(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    ok = store.save_conversation("sess-doesnt-matter", CLIENT_A, copy.deepcopy(store._DEFAULT_CONVERSATION))
    assert ok is False


def test_ttl_is_set_on_save(fake_client):
    session_id = "sess-ttl-check"
    store.save_conversation(session_id, CLIENT_A, copy.deepcopy(store._DEFAULT_CONVERSATION))

    ttl = fake_client.ttl(store._key(session_id, CLIENT_A))
    assert ttl > 0
    assert ttl <= store.SESSION_TTL_SECONDS


def test_corrupted_entry_returns_fresh_default_not_a_crash(fake_client):
    session_id = "sess-corrupted"
    fake_client.set(store._key(session_id, CLIENT_A), "{not valid json::")
    loaded = store.load_conversation(session_id, CLIENT_A)
    assert loaded == store._DEFAULT_CONVERSATION


def test_delete_conversation_removes_key(fake_client):
    session_id = "sess-to-delete"
    store.save_conversation(session_id, CLIENT_A, copy.deepcopy(store._DEFAULT_CONVERSATION))
    assert fake_client.get(store._key(session_id, CLIENT_A)) is not None

    ok = store.delete_conversation(session_id, CLIENT_A)
    assert ok is True
    assert fake_client.get(store._key(session_id, CLIENT_A)) is None


def test_delete_when_redis_unreachable_returns_false(monkeypatch):
    monkeypatch.setattr(store, "_client", _AlwaysDownClient())
    ok = store.delete_conversation("sess-doesnt-matter", CLIENT_A)
    assert ok is False


def test_missing_new_field_merges_over_default(fake_client):
    session_id = "sess-old-schema"
    old_shape = {"last_topic": "old topic", "last_platform": "instagram"}
    fake_client.set(store._key(session_id, CLIENT_A), json.dumps(old_shape))

    loaded = store.load_conversation(session_id, CLIENT_A)
    assert loaded["last_topic"] == "old topic"
    assert loaded["gate_tokens_used"] == 0
    assert loaded["message_history"] == []


# --- Phase 4: client scoping --------------------------------------------

def test_different_client_same_session_id_gets_fresh_default():
    session_id = "shared-session-id"
    a_data = copy.deepcopy(store._DEFAULT_CONVERSATION)
    a_data["last_topic"] = "client A's private topic"
    store.save_conversation(session_id, CLIENT_A, a_data)

    b_view = store.load_conversation(session_id, CLIENT_B)
    assert b_view == store._DEFAULT_CONVERSATION
    assert b_view["last_topic"] is None  # never sees A's data


def test_same_client_same_session_id_gets_own_data_back():
    session_id = "shared-session-id"
    a_data = copy.deepcopy(store._DEFAULT_CONVERSATION)
    a_data["last_topic"] = "client A's private topic"
    store.save_conversation(session_id, CLIENT_A, a_data)

    a_view = store.load_conversation(session_id, CLIENT_A)
    assert a_view["last_topic"] == "client A's private topic"


def test_cross_client_delete_is_a_noop_and_returns_true():
    session_id = "shared-session-id"
    a_data = copy.deepcopy(store._DEFAULT_CONVERSATION)
    a_data["last_topic"] = "client A's private topic"
    store.save_conversation(session_id, CLIENT_A, a_data)

    # Client B "deletes" a session_id it never owned
    ok = store.delete_conversation(session_id, CLIENT_B)
    assert ok is True  # no error revealing the ownership mismatch

    # Client A's actual data must be completely untouched
    a_view_after = store.load_conversation(session_id, CLIENT_A)
    assert a_view_after["last_topic"] == "client A's private topic"