"""api/web/dependencies/auth_deps.py -- FastAPI authentication dependencies."""
import os
import secrets
from typing import Optional, Dict
import jwt
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.environ.get("JWT_SECRET", "trendforge_default_secret_key_change_in_prod")
JWT_ALGORITHM = "HS256"
GENERIC_TOKEN_ERROR = "Invalid or missing token"


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

    # Transient fallback ID if headers were omitted
    return f"anon:{secrets.token_hex(8)}"
