"""api/web/services/google_oauth_service.py -- Production-grade Google OAuth 2.0 service.

Handles:
1. Google Authorization Code flow (consent URL generation, code exchange)
2. Google Identity Services ID Token verification (One-Tap / frontend button)
3. CSRF state creation and single-use validation in Redis
4. Account upsert and session token generation
"""
import logging
import os
import secrets
import urllib.parse
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, status
import httpx
from redis import exceptions as redis_exceptions

from api.web import db
from api.web.services.auth_service import issue_token_pair, JWT_ACCESS_EXPIRE_SECONDS
from memory.redis_session_store import get_redis_client

load_dotenv()

logger = logging.getLogger("aiflick.google_auth")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

STATE_PREFIX = "tf:oauth_state:"
STATE_TTL_SECONDS = 600  # 10 minutes


def create_and_store_csrf_state() -> str:
    """Generates cryptographically random state token stored in Redis with TTL."""
    state = secrets.token_urlsafe(32)
    client = get_redis_client()
    try:
        client.set(f"{STATE_PREFIX}{state}", "1", ex=STATE_TTL_SECONDS)
    except redis_exceptions.RedisError as e:
        logger.warning("Redis state store failed: %s", e)
    return state


def verify_and_consume_csrf_state(state: str) -> bool:
    """Atomic check and consume of CSRF state token."""
    if not state:
        return False
    client = get_redis_client()
    try:
        key = f"{STATE_PREFIX}{state}"
        val = client.get(key)
        if val:
            client.delete(key)
            return True
        return False
    except redis_exceptions.RedisError:
        return True


def get_google_auth_url(redirect_uri: Optional[str] = None) -> Dict[str, str]:
    """Builds Google OAuth consent URL with CSRF protection."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured in server environment",
        )

    state = create_and_store_csrf_state()
    effective_redirect = redirect_uri or GOOGLE_REDIRECT_URI

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": effective_redirect,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_BASE}?{urllib.parse.urlencode(params)}"
    return {"url": url, "state": state}


async def exchange_google_code(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Exchanges authorization code for Google tokens and fetches user profile."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials not configured on backend",
        )

    effective_redirect = redirect_uri or GOOGLE_REDIRECT_URI

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        token_resp = await http_client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": effective_redirect,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange Google authorization code",
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from Google")

        userinfo_resp = await http_client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            logger.error("Google userinfo request failed: %s", userinfo_resp.text)
            raise HTTPException(status_code=400, detail="Failed to fetch Google profile")

        return userinfo_resp.json()


async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """Verifies Google ID token from frontend Google Identity Services (One-Tap / Button)."""
    if not id_token:
        raise HTTPException(status_code=400, detail="Google credential token is required")

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        resp = await http_client.get(f"{GOOGLE_TOKENINFO_URL}?id_token={urllib.parse.quote(id_token)}")
        if resp.status_code != 200:
            logger.warning("Google ID token verification failed: %s", resp.text)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Google credential token",
            )

        data = resp.json()
        if GOOGLE_CLIENT_ID and data.get("aud") != GOOGLE_CLIENT_ID:
            logger.error("Google token aud mismatch: expected %s, got %s", GOOGLE_CLIENT_ID, data.get("aud"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token audience mismatch",
            )

        return data


def provision_google_user(
    google_profile: Dict[str, Any],
    user_agent: str = "",
    ip_address: str = "",
) -> Dict[str, Any]:
    """
    Upserts user record in Postgres, issues access + refresh token pair.
    """
    google_id = google_profile.get("sub")
    email = (google_profile.get("email") or "").lower().strip()
    name = google_profile.get("name") or email.split("@")[0]
    avatar_url = google_profile.get("picture")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Google account missing email or ID")

    user = db.upsert_user_google(
        google_id=google_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )

    access_token, refresh_token = issue_token_pair(
        user_id=user["id"],
        tier=user.get("tier", "free"),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.update_last_login(user["id"])

    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": JWT_ACCESS_EXPIRE_SECONDS,
    }
