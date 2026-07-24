"""
web/deps.py -- session id resolution.

Resolution order, highest priority first:
1. Explicit session_id in the request body -- required for any non-browser
   client (Slack bot, mobile app, another backend service) that has no
   cookie jar and needs to own its own session identity.
2. The tf_session_id cookie -- convenience for a plain browser client that
   never wants to think about session ids at all.
3. Neither present -- mint a new one and set the cookie (browser-friendly
   default), and return it in the response body too (so non-browser
   clients calling the same endpoint without a cookie jar still get the id
   back and can pass it explicitly on the next call).

This satisfies the master doc's literal contract (session_id is a request/
response concept, not something hidden purely in a cookie) while staying
convenient for a plain web frontend.
"""
import uuid
from typing import Optional

from fastapi import Request, Response

SESSION_COOKIE_NAME = "tf_session_id"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 48  # 48h -- cookie lifetime, independent of the Redis TTL


def resolve_session_id(request: Request, response: Response, explicit_session_id: Optional[str]) -> str:
    if explicit_session_id:
        return explicit_session_id

    cookie_session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_session_id:
        return cookie_session_id

    new_id = uuid.uuid4().hex
    response.set_cookie(
        SESSION_COOKIE_NAME, new_id,
        httponly=True, samesite="lax", max_age=SESSION_COOKIE_MAX_AGE,
    )
    return new_id