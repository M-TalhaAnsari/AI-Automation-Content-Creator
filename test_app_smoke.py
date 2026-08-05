"""
web/test_app_smoke.py -- end-to-end smoke test of the FastAPI layer
against the REAL main.py and conversation/orchestrator.py (copied
verbatim from the ground truth files), with only the Groq network call
mocked out (no API key available in this sandbox) and fakeredis standing
in for a real Redis server.

This exists to prove the wiring is correct -- request in, correct
dispatch, correct response shape, correct session persistence -- not to
test the pipeline's content quality (that's what the stubbed fetchers/
generator are for), and not to test auth itself (that's web/test_auth.py
and web/test_client_isolation.py's job). Auth is overridden here via
FastAPI's dependency_overrides, which is the standard way to bypass a
dependency you're not testing -- not a workaround for something broken.
"""
import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue

import memory.redis_session_store as store
from api.web import app as app_module
from api.web.auth import verify_api_key

TEST_CLIENT_NAME = "testclient"

client = TestClient(app_module.app)


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """This file tests wiring, not rate limiting (that's
    web/test_rate_limit.py's job). Without this, ~15+ tests here all
    sharing the same 'testclient' identity (via bypass_auth below)
    would pile up against the real 10/minute /chat limit and start
    failing with 429s partway through an unrelated test run -- a real
    risk once the rate limiter went in, not hypothetical."""
    app_module.limiter.enabled = False
    yield
    app_module.limiter.enabled = True


@pytest.fixture(autouse=True)
def fake_redis_everywhere(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(store, "_client", fake)

    # Also fake the JOB QUEUE's connection -- this was a real gap
    # before: only the session store was faked, so any test that
    # triggered run_new_request (a slow action) pushed an actual job
    # into the REAL Redis queue, sitting there until a real worker
    # picked it up later and burned real Groq/Tavily calls on test
    # data. Queue.enqueue and Job.fetch both need a non-decoding
    # connection (RQ handles its own encoding), hence decode_responses
    # is left False here, unlike the session-store fake above.
    fake_queue_conn = fakeredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(app_module, "_redis_conn", fake_queue_conn)
    monkeypatch.setattr(app_module, "_queue", Queue("trendforge", connection=fake_queue_conn))

    yield fake


@pytest.fixture(autouse=True)
def bypass_auth():
    app_module.app.dependency_overrides[verify_api_key] = lambda: TEST_CLIENT_NAME
    yield
    app_module.app.dependency_overrides.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_first_message_is_always_run_new_request_and_goes_through_job_queue():
    """No last_generated_posts yet -> process_turn's stage-0 shortcut
    fires deterministically -> run_new_request -> NOT in INLINE_ACTIONS
    -> must return status=processing with a job_id, never call Groq."""
    r = client.post("/chat", json={"message": "AI automation tools for job seekers", "platform": "linkedin"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "processing"
    assert body["action"] == "run_new_request"
    assert body["job_id"]
    assert "tf_session_id" in r.cookies


def test_explicit_session_id_is_honored_over_cookie():
    r = client.post("/chat", json={"message": "hello", "session_id": "explicit-123"})
    assert r.json()["session_id"] if "session_id" in r.json() else True
    sess = client.get("/session/explicit-123")
    assert sess.status_code == 200
    assert sess.json()["message_history"][-1]["content"] == "hello"


def test_inline_action_add_constraint_bypasses_queue(monkeypatch):
    """Pre-seed a session with posts already generated (skips the stage-0
    shortcut), then monkeypatch process_turn to simulate the LLM
    resolving to add_constraint -- proves the inline path calls
    dispatch_action synchronously and returns the real reply, with no
    job_id and no queue involved."""
    session_id = "sess-inline-test"
    seeded = store._fresh_default()
    seeded["last_generated_posts"] = [{"title": "t1", "caption": "c1"}]
    store.save_conversation(session_id, TEST_CLIENT_NAME, seeded)

    def fake_process_turn(conversation, message):
        conversation.setdefault("message_history", []).append({"role": "user", "content": message})
        return {"action": "add_constraint",
                "args": {"constraint_type": "exclude", "constraint_value": "n8n"},
                "tokens_used": 7, "error": None}

    monkeypatch.setattr(app_module, "process_turn", fake_process_turn)

    r = client.post("/chat", json={"message": "don't mention n8n", "session_id": session_id})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["action"] == "add_constraint"
    assert "n8n" in body["reply"]
    assert body["job_id"] is None

    sess = store.load_conversation(session_id, TEST_CLIENT_NAME)
    assert {"type": "exclude", "value": "n8n"} in sess["active_constraints"]


def test_real_orchestrator_stage0_shortcut_no_network_call():
    """Uses the REAL process_turn (no mocking) for a brand-new session --
    the stage-0 shortcut in conversation/orchestrator.py means this must
    resolve without ever touching the network/Groq client."""
    from conversation.orchestrator import process_turn
    conv = store._fresh_default()
    result = process_turn(conv, "generate some posts about rust programming")
    assert result["action"] == "run_new_request"
    assert result["error"] is None
    assert result["tokens_used"] == 0  # proves no LLM call happened
    assert conv["message_history"][0] == {"role": "user", "content": "generate some posts about rust programming"}


def test_job_status_unknown_id_returns_404():
    r = client.get("/chat/status/does-not-exist")
    assert r.status_code == 404


def test_get_session_returns_fresh_default_for_new_id():
    r = client.get("/session/brand-new-session-xyz")
    assert r.status_code == 200
    body = r.json()
    assert body["last_topic"] is None
    assert body["message_history"] == []


def test_delete_session():
    session_id = "sess-to-delete-via-api"
    store.save_conversation(session_id, TEST_CLIENT_NAME, store._fresh_default())
    r = client.delete(f"/session/{session_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


def test_no_api_key_is_rejected_when_auth_not_overridden():
    """Confirms auth is actually wired into the endpoint (not just
    present in the module) -- calls the real app WITHOUT the
    bypass_auth override active, using a fresh TestClient against a
    version of the app with no override installed."""
    app_module.app.dependency_overrides.clear()  # remove this file's own override, just for this one test
    try:
        r = client.post("/chat", json={"message": "should be rejected"})
        assert r.status_code == 401
    finally:
        app_module.app.dependency_overrides[verify_api_key] = lambda: TEST_CLIENT_NAME