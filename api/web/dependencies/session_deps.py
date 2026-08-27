"""api/web/dependencies/session_deps.py -- Session ID resolution dependency."""
import uuid
from typing import Optional
from fastapi import Request, Response


def resolve_session_id(
    request: Request,
    response: Response,
    body_session_id: Optional[str] = None,
) -> str:
    if body_session_id:
        return body_session_id
    cookie_id = request.cookies.get("trendforge_session")
    if cookie_id:
        return cookie_id
    new_id = str(uuid.uuid4())
    response.set_cookie("trendforge_session", new_id, httponly=True, samesite="lax")
    return new_id
