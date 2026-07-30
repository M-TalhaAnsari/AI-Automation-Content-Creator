"""
web/test_rate_limit.py

Tests the rate-limiting MECHANISM in isolation -- a small standalone
FastAPI app using the real limiter, key function, and exception handler
from web/rate_limit.py, backed by an in-memory store (per the master
doc's own instruction: Split B's tests should not require a real Redis/
Docker stack). The full, real integration test -- hitting the actual
/chat endpoint through real Docker containers and real Redis -- is a
separate, later verification step (Phase 5 master doc, section 5),
which needs an actual docker-compose stack to mean anything.

Covers the 4 required cases:
1. Client A can make requests up to the limit, succeeds
2. Client A's next request past the limit -> 429 with the exact
   response shape from the master doc
3. Client B (different client_name) is unaffected by Client A hitting
   their limit -- proves per-CLIENT scoping, not global or per-IP
4. The 429 response's retry_after_seconds is a real computed value,
   not hardcoded
"""
import time

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from web.rate_limit import get_client_identity, rate_limit_exceeded_handler

LOW_LIMIT = "3/minute"  # small number so tests run fast and deterministically


def _build_test_app():
    """A minimal app exercising the exact same key_func and exception
    handler the real app uses, with its own in-memory-backed limiter
    instance so tests never touch real Redis and never interfere with
    each other's counters across test runs."""
    test_limiter = Limiter(
        key_func=get_client_identity,
        storage_uri="memory://",
        headers_enabled=True,
    )

    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    @test_limiter.limit(LOW_LIMIT)
    async def limited_endpoint(request: Request, response: Response):
        return {"ok": True}

    return app


@pytest.fixture
def client():
    return TestClient(_build_test_app())


def _headers(key):
    return {"X-API-Key": key}


def test_client_a_succeeds_up_to_the_limit(client, monkeypatch):
    monkeypatch.setenv("API_CLIENT_A", "key-for-client-a")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    for _ in range(3):  # LOW_LIMIT = 3/minute
        r = client.get("/limited", headers=_headers("key-for-client-a"))
        assert r.status_code == 200


def test_client_a_blocked_on_the_next_request_past_the_limit(client, monkeypatch):
    monkeypatch.setenv("API_CLIENT_A", "key-for-client-a")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    for _ in range(3):
        client.get("/limited", headers=_headers("key-for-client-a"))

    r = client.get("/limited", headers=_headers("key-for-client-a"))
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate_limit_exceeded"
    assert "retry_after_seconds" in body


def test_client_b_unaffected_by_client_a_hitting_their_limit(client, monkeypatch):
    monkeypatch.setenv("API_CLIENT_A", "key-for-client-a")
    monkeypatch.setenv("API_CLIENT_B", "key-for-client-b")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    # Exhaust client A's limit entirely
    for _ in range(3):
        client.get("/limited", headers=_headers("key-for-client-a"))
    blocked = client.get("/limited", headers=_headers("key-for-client-a"))
    assert blocked.status_code == 429

    # Client B, same endpoint, same server, completely separate bucket
    b_response = client.get("/limited", headers=_headers("key-for-client-b"))
    assert b_response.status_code == 200


def test_retry_after_seconds_is_real_not_hardcoded(client, monkeypatch):
    """Confirms retry_after_seconds actually reflects real elapsed time
    against the window, rather than being a fixed constant -- hits the
    limit, waits a couple of seconds, hits it again, and confirms the
    second retry_after_seconds is smaller (closer to the window
    resetting) than the first."""
    monkeypatch.setenv("API_CLIENT_A", "key-for-client-a")
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    for _ in range(3):
        client.get("/limited", headers=_headers("key-for-client-a"))

    first = client.get("/limited", headers=_headers("key-for-client-a"))
    assert first.status_code == 429
    first_retry = first.json()["retry_after_seconds"]

    time.sleep(2)

    second = client.get("/limited", headers=_headers("key-for-client-a"))
    assert second.status_code == 429
    second_retry = second.json()["retry_after_seconds"]

    # A fixed/hardcoded value would never change between these two
    # calls. A real one, computed against the actual window, must have
    # decreased by roughly the time we just slept.
    assert second_retry < first_retry
    assert first_retry - second_retry >= 1


def test_missing_or_unresolvable_key_falls_back_gracefully_not_crash(client, monkeypatch):
    """No API_CLIENT_* registered at all -- get_client_identity must
    fall back to a safe string, never raise, even though the request
    itself will separately 401 at the real app's auth layer (not
    relevant to this isolated app, which has no auth dependency)."""
    monkeypatch.delenv("API_CLIENT_A", raising=False)
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    r = client.get("/limited", headers=_headers("some-key-that-matches-nothing"))
    assert r.status_code == 200  # this isolated test app has no auth layer -- just proves no crash


def test_rotating_invalid_keys_cannot_bypass_the_limit(client, monkeypatch):
    """Real exploit found and fixed during Phase 6 planning: the
    fallback identity for an unresolvable key used to be the RAW key
    value itself, meaning every different garbage key got its own
    fresh, never-before-seen bucket -- an attacker rotating the key on
    every request faced NO practical rate limit at all (empirically
    confirmed: 30 requests, 30 different garbage keys, zero throttled,
    before this fix). All unresolvable/missing keys must now collapse
    into ONE shared bucket, so the aggregate volume of invalid-key
    traffic is capped at the route's normal limit -- not each attacker
    getting an unlimited personal allowance by varying the key."""
    monkeypatch.delenv("API_CLIENT_A", raising=False)
    import importlib
    from web import auth as auth_module
    importlib.reload(auth_module)
    monkeypatch.setattr("web.rate_limit.resolve_client_name", auth_module.resolve_client_name)

    statuses = []
    for i in range(10):  # LOW_LIMIT = 3/minute -- 10 different garbage keys, way over the limit
        r = client.get("/limited", headers=_headers(f"garbage-key-{i}"))
        statuses.append(r.status_code)

    assert statuses.count(200) == 3  # exactly the limit, not one success per unique key
    assert statuses.count(429) == 7