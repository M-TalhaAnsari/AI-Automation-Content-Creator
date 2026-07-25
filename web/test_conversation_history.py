"""
web/test_conversation_history.py

Two things verified here:
1. (Phase 3, updated for client_name) message_history actually
   accumulates correctly, in order, across multiple separate requests
   to the same session_id, and genuinely persists in Redis.
2. (Phase 4, new) two different REAL API keys hitting the SAME
   session_id string over real HTTP get genuinely separate
   conversations -- this is the master doc's explicit integration
   requirement (section 5, item 3): "Test with TWO different client
   keys against the SAME session_id string, confirming they get
   genuinely separate conversations."
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient

import memory.redis_session_store as store
from web import app as app_module
from web.auth import verify_api_key

TEST_CLIENT_NAME = "testclient"

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store, "_client", fake)
    yield fake


def _fake_process_turn_factory(action_sequence):
    calls = {"i": 0}

    def _fake(conversation, message):
        conversation.setdefault("message_history", []).append({"role": "user", "content": message})
        action, args = action_sequence[calls["i"]]
        calls["i"] += 1
        call_id = f"call_{calls['i']}"
        conversation["message_history"].append({
            "role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": action, "arguments": "{}"}}],
        })
        conversation["message_history"].append({
            "role": "tool", "tool_call_id": call_id, "content": f"dispatched:{action}",
        })
        return {"action": action, "args": args, "tokens_used": 5, "error": None}

    return _fake


# --- Phase 3 regression: history accumulates correctly across turns ----

@pytest.fixture(autouse=True)
def bypass_auth():
    app_module.app.dependency_overrides[verify_api_key] = lambda: TEST_CLIENT_NAME
    yield
    app_module.app.dependency_overrides.clear()


def test_history_accumulates_correctly_across_three_separate_requests(monkeypatch):
    session_id = "sess-history-check"

    seeded = store._fresh_default()
    seeded["last_generated_posts"] = [{"title": "t1", "caption": "c1"}]
    store.save_conversation(session_id, TEST_CLIENT_NAME, seeded)

    fake = _fake_process_turn_factory([
        ("add_constraint", {"constraint_type": "exclude", "constraint_value": "n8n"}),
        ("add_constraint", {"constraint_type": "exclude", "constraint_value": "TensorFlow"}),
        ("remove_constraint", {"constraint_value": "n8n"}),
    ])
    monkeypatch.setattr(app_module, "process_turn", fake)

    r1 = client.post("/chat", json={"message": "don't mention n8n", "session_id": session_id})
    assert r1.status_code == 200
    assert r1.json()["action"] == "add_constraint"

    after_turn1 = store.load_conversation(session_id, TEST_CLIENT_NAME)
    assert len(after_turn1["message_history"]) == 3
    assert after_turn1["active_constraints"] == [{"type": "exclude", "value": "n8n"}]

    r2 = client.post("/chat", json={"message": "also exclude TensorFlow", "session_id": session_id})
    assert r2.status_code == 200

    after_turn2 = store.load_conversation(session_id, TEST_CLIENT_NAME)
    assert len(after_turn2["message_history"]) == 6
    assert after_turn2["active_constraints"] == [
        {"type": "exclude", "value": "n8n"},
        {"type": "exclude", "value": "TensorFlow"},
    ]

    r3 = client.post("/chat", json={"message": "actually n8n is fine now", "session_id": session_id})
    assert r3.status_code == 200

    after_turn3 = store.load_conversation(session_id, TEST_CLIENT_NAME)
    assert len(after_turn3["message_history"]) == 9
    assert after_turn3["active_constraints"] == [{"type": "exclude", "value": "TensorFlow"}]
    roles = [m["role"] for m in after_turn3["message_history"]]
    assert roles == ["user", "assistant", "tool"] * 3


def test_history_isolated_between_different_sessions_same_client(monkeypatch):
    """Two different session_ids under the SAME client -- must never
    leak into each other. (Cross-CLIENT isolation is tested separately
    below with real API keys, no dependency override.)"""
    fake_a = _fake_process_turn_factory([("add_constraint", {"constraint_type": "exclude", "constraint_value": "A-only"})])
    fake_b = _fake_process_turn_factory([("add_constraint", {"constraint_type": "exclude", "constraint_value": "B-only"})])

    for sid in ("sess-A", "sess-B"):
        seeded = store._fresh_default()
        seeded["last_generated_posts"] = [{"title": "t", "caption": "c"}]
        store.save_conversation(sid, TEST_CLIENT_NAME, seeded)

    monkeypatch.setattr(app_module, "process_turn", fake_a)
    client.post("/chat", json={"message": "for session A", "session_id": "sess-A"})

    monkeypatch.setattr(app_module, "process_turn", fake_b)
    client.post("/chat", json={"message": "for session B", "session_id": "sess-B"})

    sess_a = store.load_conversation("sess-A", TEST_CLIENT_NAME)
    sess_b = store.load_conversation("sess-B", TEST_CLIENT_NAME)

    assert sess_a["active_constraints"] == [{"type": "exclude", "value": "A-only"}]
    assert sess_b["active_constraints"] == [{"type": "exclude", "value": "B-only"}]


# --- Phase 4: cross-CLIENT isolation, over real HTTP, real API keys ----

def test_two_different_api_keys_same_session_id_get_genuinely_separate_conversations(monkeypatch):
    """The master doc's explicit integration requirement: two different
    client keys hitting the exact same session_id string must not see
    each other's data. Uses the REAL verify_api_key logic (unmocked)
    with two real registered keys -- dependency_overrides is used only
    because Python's import/reload semantics mean a freshly-reloaded
    module produces a NEW function object that app.py's already-
    registered routes don't automatically pick up; the override points
    the route at that fresh function so the real, current registry is
    what actually runs, not a shortcut around testing it."""
    app_module.app.dependency_overrides.clear()

    monkeypatch.setenv("API_CLIENT_WEB", "web-real-key")
    monkeypatch.setenv("API_CLIENT_SLACK", "slack-real-key")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)  # rebuilds _API_CLIENTS from the env vars just set

    from web.auth import verify_api_key as route_registered_dependency
    app_module.app.dependency_overrides[route_registered_dependency] = auth_module.verify_api_key

    same_session_id = "shared-across-clients"

    resp_web = client.post(
        "/chat",
        json={"message": "web client's message", "session_id": same_session_id},
        headers={"X-API-Key": "web-real-key"},
    )
    resp_slack = client.post(
        "/chat",
        json={"message": "slack client's message", "session_id": same_session_id},
        headers={"X-API-Key": "slack-real-key"},
    )
    assert resp_web.status_code == 200
    assert resp_slack.status_code == 200

    web_session = client.get(f"/session/{same_session_id}", headers={"X-API-Key": "web-real-key"})
    slack_session = client.get(f"/session/{same_session_id}", headers={"X-API-Key": "slack-real-key"})

    web_messages = [m["content"] for m in web_session.json()["message_history"] if m["role"] == "user"]
    slack_messages = [m["content"] for m in slack_session.json()["message_history"] if m["role"] == "user"]

    assert web_messages == ["web client's message"]
    assert slack_messages == ["slack client's message"]
    # Cross-check: web's key can't see slack's session content even
    # though it's asking for the literal same session_id string
    assert "slack client's message" not in web_messages
    assert "web client's message" not in slack_messages

    app_module.app.dependency_overrides.clear()


def test_wrong_or_missing_key_rejected_with_real_auth(monkeypatch):
    app_module.app.dependency_overrides.clear()
    monkeypatch.setenv("API_CLIENT_WEB", "web-real-key")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)

    from web.auth import verify_api_key as route_registered_dependency
    app_module.app.dependency_overrides[route_registered_dependency] = auth_module.verify_api_key

    no_key = client.post("/chat", json={"message": "test"})
    wrong_key = client.post("/chat", json={"message": "test"}, headers={"X-API-Key": "not-a-real-key"})

    assert no_key.status_code == 401
    assert wrong_key.status_code == 401
    assert no_key.json()["detail"] == wrong_key.json()["detail"]

    app_module.app.dependency_overrides.clear()


def test_job_status_rejects_wrong_client_same_as_unknown_job(monkeypatch):
    """A job belongs to whichever client enqueued it (see meta= in
    web/app.py's /chat). A different client polling that job_id must
    get the IDENTICAL 404 as a genuinely unknown job_id -- never a
    distinguishable error that would reveal the job exists for someone
    else. This closes a gap flagged earlier: no test existed for the
    job-status scoping logic itself."""
    app_module.app.dependency_overrides.clear()
    monkeypatch.setenv("API_CLIENT_WEB", "web-real-key")
    monkeypatch.setenv("API_CLIENT_SLACK", "slack-real-key")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    from web.auth import verify_api_key as route_registered_dependency
    app_module.app.dependency_overrides[route_registered_dependency] = auth_module.verify_api_key

    # Fresh session -> stage-0 shortcut -> real process_turn resolves to
    # run_new_request without touching Groq -> goes through the real queue.
    resp = client.post(
        "/chat",
        json={"message": "test", "session_id": "sess-job-scoping"},
        headers={"X-API-Key": "web-real-key"},
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert job_id

    # The owning client can see its own job.
    own_status = client.get(f"/chat/status/{job_id}", headers={"X-API-Key": "web-real-key"})
    assert own_status.status_code == 200

    # A different client gets the SAME 404 as a genuinely unknown job_id.
    other_status = client.get(f"/chat/status/{job_id}", headers={"X-API-Key": "slack-real-key"})
    unknown_status = client.get("/chat/status/not-a-real-job-id", headers={"X-API-Key": "slack-real-key"})
    assert other_status.status_code == 404
    assert unknown_status.status_code == 404
    assert other_status.json()["detail"] == unknown_status.json()["detail"]

    app_module.app.dependency_overrides.clear()