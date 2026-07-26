"""
web/test_auth.py

Covers the 5 cases the Phase 4 master doc requires for Split A, plus a
couple of edge cases (env var name containing an underscore in the
client name, empty-string key value) worth pinning down since they're
easy to get subtly wrong in the prefix-parsing logic.

verify_api_key is an async function (required so it works as a FastAPI
dependency), but these tests call it directly via asyncio.run() rather
than pulling in pytest-asyncio for one file's worth of tests.
"""
import asyncio
import importlib
import os

import pytest
from fastapi import HTTPException

from web import auth as auth_module


def _reload_with_env(monkeypatch, env: dict):
    """Clears any existing API_CLIENT_* vars, sets the given ones, then
    reloads the module so its registry is rebuilt from a known state --
    mirrors how the real registry is only ever read once at import
    time, so each test gets a clean, deterministic starting point."""
    for key in list(os.environ.keys()):
        if key.startswith(auth_module.PREFIX):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(auth_module)
    return auth_module


def _verify(mod, key):
    return asyncio.run(mod.verify_api_key(x_api_key=key))


def test_valid_key_returns_correct_client_name(monkeypatch):
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_WEB": "web-secret-key"})
    assert _verify(mod, "web-secret-key") == "web"


def test_missing_header_raises_401(monkeypatch):
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_WEB": "web-secret-key"})
    with pytest.raises(HTTPException) as exc_info:
        _verify(mod, None)
    assert exc_info.value.status_code == 401


def test_unregistered_key_raises_401(monkeypatch):
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_WEB": "web-secret-key"})
    with pytest.raises(HTTPException) as exc_info:
        _verify(mod, "not-a-real-key")
    assert exc_info.value.status_code == 401


def test_two_different_keys_return_two_different_client_names(monkeypatch):
    mod = _reload_with_env(monkeypatch, {
        "API_CLIENT_WEB": "web-secret-key",
        "API_CLIENT_SLACK": "slack-secret-key",
    })
    assert _verify(mod, "web-secret-key") == "web"
    assert _verify(mod, "slack-secret-key") == "slack"


def test_empty_registry_rejects_every_request(monkeypatch):
    mod = _reload_with_env(monkeypatch, {})
    with pytest.raises(HTTPException) as exc_info:
        _verify(mod, "anything-at-all")
    assert exc_info.value.status_code == 401


def test_missing_vs_wrong_key_give_identical_error_message(monkeypatch):
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_WEB": "web-secret-key"})
    with pytest.raises(HTTPException) as missing:
        _verify(mod, None)
    with pytest.raises(HTTPException) as wrong:
        _verify(mod, "totally-wrong")
    assert missing.value.detail == wrong.value.detail


def test_client_name_with_underscore_parses_correctly(monkeypatch):
    """API_CLIENT_MOBILE_V2 must become client_name 'mobile_v2', not be
    mangled by a naive split on every underscore."""
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_MOBILE_V2": "mobile-v2-key"})
    assert mod.get_api_clients() == {"mobile_v2": "mobile-v2-key"}


def test_empty_string_value_is_ignored(monkeypatch):
    mod = _reload_with_env(monkeypatch, {"API_CLIENT_WEB": ""})
    assert mod.get_api_clients() == {}