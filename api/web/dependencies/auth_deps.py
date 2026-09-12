"""api/web/dependencies/auth_deps.py -- FastAPI authentication dependencies."""
import os
import secrets
from typing import Optional
from fastapi import Header, HTTPException, status
from dotenv import load_dotenv

from api.web.services.auth_service import verify_access_token

load_dotenv()

GENERIC_TOKEN_ERROR = "Invalid or missing token"


async def verify_jwt(authorization: Optional[str] = Header(None)) -> str:
    """Verifies Bearer JWT, checking expiration and Redis revocation blocklist."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_TOKEN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer "):].strip()
    payload = verify_access_token(token)
    return payload["sub"]


def get_current_user_id(client_name: str) -> int:
    """Extracts integer user ID from client_name formatted 'user:{id}'."""
    if not client_name.startswith("user:"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identity required for this operation",
        )
    try:
        return int(client_name.split(":", 1)[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed user identity")


async def verify_identity(
    authorization: Optional[str] = Header(None),
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
) -> str:
    """Accepts either a logged-in user (Bearer JWT) or an anonymous guest (X-Anon-Id)."""
    if authorization and authorization.startswith("Bearer "):
        try:
            return await verify_jwt(authorization=authorization)
        except HTTPException:
            if not x_anon_id:
                raise

    if x_anon_id:
        from api.web import anon_trial
        if anon_trial.is_over_limit(x_anon_id):
            raise HTTPException(status_code=403, detail="signup_required")
        return f"anon:{x_anon_id}"

    # Fallback temporary guest ID
    return f"anon:{secrets.token_hex(8)}"

