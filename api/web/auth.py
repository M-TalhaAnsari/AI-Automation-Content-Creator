"""web/auth.py -- API-key auth (existing, for future non-browser clients)
plus JWT + password auth (delegating to production-grade auth_service & auth_deps).
"""
import os
import secrets
from typing import Dict, Optional

from dotenv import load_dotenv

from api.web.dependencies.auth_deps import verify_identity, verify_jwt, get_current_user_id
from api.web.services.auth_service import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_ACCESS_EXPIRE_SECONDS,
    hash_password,
    verify_password,
    create_access_token as create_jwt,
)

load_dotenv()

PREFIX = "API_CLIENT_"
GENERIC_AUTH_ERROR = "Invalid or missing API key"
GENERIC_TOKEN_ERROR = "Invalid or missing token"


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


async def verify_api_key(x_api_key: Optional[str] = None) -> str:
    client_name = resolve_client_name(x_api_key)
    if client_name is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)
    return client_name


def resolve_client_name(api_key: Optional[str]) -> Optional[str]:
    if not api_key:
        return None
    for client_name, registered_key in _API_CLIENTS.items():
        if secrets.compare_digest(api_key, registered_key):
            return client_name
    return None