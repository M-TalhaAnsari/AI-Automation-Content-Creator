"""
web/auth.py -- per-client API key authentication.

Loads API_CLIENT_<NAME>=<key> environment variables into a registry at
import time, and exposes verify_api_key as a FastAPI dependency that
every protected endpoint uses via Depends(verify_api_key).

Design notes (Phase 4 master doc, section 2):
- Fail closed: an empty registry (no API_CLIENT_* vars set) rejects
  every request. The safe failure direction is "nobody gets in", not
  "everybody gets in".
- Constant-time comparison: uses secrets.compare_digest instead of `==`
  to avoid a timing side-channel on the key comparison itself.
- Same generic 401 message for "no header", "empty header", and
  "header present but not a registered key" -- never let the response
  reveal which of those three happened.
- client_name is derived from the env var name, lowercased
  (API_CLIENT_SLACK -> "slack"), independent of the key VALUE itself
  (which is compared as an opaque secret, never case-folded).
"""
import os
import secrets
from typing import Dict, Optional

from fastapi import Header, HTTPException

PREFIX = "API_CLIENT_"
GENERIC_AUTH_ERROR = "Invalid or missing API key"


def get_api_clients() -> Dict[str, str]:
    """
    Parses every API_CLIENT_<NAME> env var into {client_name: key}.

    Splits on the fixed PREFIX length, not on "_", so a client literally
    named e.g. MOBILE_V2 (env var API_CLIENT_MOBILE_V2) becomes
    client_name "mobile_v2" correctly instead of being mangled by a
    naive split("_")[1].

    Never raises. An empty dict (no matching env vars) is a valid,
    meaningful result -- it's what makes fail-closed work.
    """
    clients: Dict[str, str] = {}
    for env_name, value in os.environ.items():
        if not env_name.startswith(PREFIX):
            continue
        if not value:
            continue
        client_name = env_name[len(PREFIX):].lower()
        if client_name:
            clients[client_name] = value
    return clients


# Loaded once at import time -- matches how every other secret in this
# project (GROQ_API_KEY, GEMINI_API_KEY) is read once at startup, not
# re-read from the environment on every request.
_API_CLIENTS: Dict[str, str] = get_api_clients()


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    FastAPI dependency. Attach via Depends(verify_api_key) to every
    protected endpoint. Returns the CLIENT NAME on success.

    Missing header, empty header, or a key not in the registry all
    raise the exact same 401 with the exact same message -- the two
    failure paths are indistinguishable from the outside on purpose.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)

    for client_name, registered_key in _API_CLIENTS.items():
        if secrets.compare_digest(x_api_key, registered_key):
            return client_name

    raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)