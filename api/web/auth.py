"""web/auth.py -- API-key auth (existing, for future non-browser clients)
plus JWT + password auth (Phase 7, used by the real frontend)."""
import os
import secrets
import time
from typing import Dict, Optional

from dotenv import load_dotenv
load_dotenv()

import bcrypt
import jwt
from fastapi import Header, HTTPException

PREFIX = "API_CLIENT_"
GENERIC_AUTH_ERROR = "Invalid or missing API key"
GENERIC_TOKEN_ERROR = "Invalid or missing token"

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 24 * 30


def get_api_clients() -> Dict[str, str]:
    clients: Dict[str, str] = {}
    for env_name, value in os.environ.items():
        if not env_name.startswith(PREFIX) or not value:
            continue
        client_name = env_name[len(PREFIX):].lower()
        if client_name:
            clients[client_name] = value
    return clients


_API_CLIENTS: Dict[str, str] = get_api_clients()


async def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    client_name = resolve_client_name(x_api_key)
    if client_name is None:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)
    return client_name


def resolve_client_name(api_key: Optional[str]) -> Optional[str]:
    if not api_key:
        return None
    for client_name, registered_key in _API_CLIENTS.items():
        if secrets.compare_digest(api_key, registered_key):
            return client_name
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_jwt(user_id: int) -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not set -- cannot issue tokens")
    payload = {"sub": f"user:{user_id}", "exp": int(time.time()) + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def verify_jwt(authorization: Optional[str] = Header(None)) -> str:
    if not JWT_SECRET or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=GENERIC_TOKEN_ERROR)
    token = authorization[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail=GENERIC_TOKEN_ERROR)
    return payload["sub"]


async def verify_identity(
    authorization: Optional[str] = Header(None),
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
) -> str:
    """Accepts either a real logged-in user (Bearer JWT) or a pre-login
    guest (X-Anon-Id) -- Phase 8. A guest past the trial limit is rejected
    with a distinct "signup_required" detail so the frontend can show a
    real prompt instead of a generic auth failure."""
    if authorization:
        return await verify_jwt(authorization=authorization)

    if not x_anon_id:
        raise HTTPException(status_code=401, detail=GENERIC_TOKEN_ERROR)

    from api.web import anon_trial
    if anon_trial.is_over_limit(x_anon_id):
        raise HTTPException(status_code=403, detail="signup_required")
    return f"anon:{x_anon_id}"