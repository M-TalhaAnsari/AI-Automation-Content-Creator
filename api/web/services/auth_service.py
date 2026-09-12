"""api/web/services/auth_service.py -- Production-grade authentication, JWT management,
token rotation, revocation, and Redis-backed blocklisting.
"""
from datetime import datetime, timedelta, timezone
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

import bcrypt
from dotenv import load_dotenv
from fastapi import HTTPException, status
import jwt
from redis import exceptions as redis_exceptions

from api.web import db
from memory.redis_session_store import get_redis_client

load_dotenv()

logger = logging.getLogger("aiflick.auth")

JWT_SECRET = os.environ.get("JWT_SECRET", "trendforge_default_secret_key_change_in_prod")
JWT_ALGORITHM = "HS256"

JWT_ACCESS_EXPIRE_SECONDS = int(os.environ.get("JWT_ACCESS_EXPIRE_MINUTES", 15)) * 60
JWT_REFRESH_EXPIRE_SECONDS = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", 7)) * 24 * 60 * 60

BLOCKLIST_PREFIX = "tf:blocklist:jti:"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Access Token (JWT)
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, tier: str = "free") -> str:
    now = int(time.time())
    jti = secrets.token_hex(16)
    payload = {
        "sub": f"user:{user_id}",
        "tier": tier,
        "jti": jti,
        "iat": now,
        "exp": now + JWT_ACCESS_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if jti and is_jti_blocked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def is_jti_blocked(jti: str) -> bool:
    client = get_redis_client()
    try:
        return bool(client.exists(f"{BLOCKLIST_PREFIX}{jti}"))
    except redis_exceptions.RedisError:
        return False


def block_access_token(token: str) -> None:
    """Extract jti and add to Redis blocklist with the remaining token TTL."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        remaining_ttl = max(1, int(exp - time.time()))
        if jti:
            client = get_redis_client()
            client.set(f"{BLOCKLIST_PREFIX}{jti}", "1", ex=remaining_ttl)
    except Exception as e:
        logger.debug("Failed to block access token: %s", e)


# ---------------------------------------------------------------------------
# Refresh Token & Token Rotation
# ---------------------------------------------------------------------------

def issue_token_pair(
    user_id: int,
    tier: str = "free",
    family: Optional[str] = None,
    user_agent: str = "",
    ip_address: str = "",
) -> Tuple[str, str]:
    """Issues (access_token, raw_refresh_token)."""
    access_token = create_access_token(user_id, tier)
    token_family = family or secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=JWT_REFRESH_EXPIRE_SECONDS)

    refresh_token = db.create_refresh_token(
        user_id=user_id,
        family=token_family,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return access_token, refresh_token


def rotate_refresh_token(
    raw_refresh_token: str,
    user_agent: str = "",
    ip_address: str = "",
) -> Dict[str, Any]:
    """
    Implements Refresh Token Rotation with theft detection.
    If an already-revoked token is used, the whole family is revoked.
    """
    token_rec = db.get_refresh_token(raw_refresh_token)
    if not token_rec:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    family = token_rec["family"]
    user_id = token_rec["user_id"]

    # THEFT DETECTION: An already revoked token is being presented
    if token_rec["is_revoked"]:
        logger.warning("🚨 Potential token theft detected! Revoking family %s for user %s", family, user_id)
        db.revoke_token_family(family)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All sessions in this family have been terminated for security.",
        )

    # Expiry check
    expires_at = token_rec["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.revoke_refresh_token(raw_refresh_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
        )

    # 1. Revoke the old refresh token
    db.revoke_refresh_token(raw_refresh_token)

    # 2. Fetch fresh user info
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 3. Issue new pair keeping the same family
    new_access_token, new_refresh_token = issue_token_pair(
        user_id=user_id,
        tier=user.get("tier", "free"),
        family=family,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in": JWT_ACCESS_EXPIRE_SECONDS,
        "user": user,
    }


# ---------------------------------------------------------------------------
# High-Level Auth Workflows
# ---------------------------------------------------------------------------

def register_user(
    email: str,
    password: str,
    name: Optional[str] = "",
    user_agent: str = "",
    ip_address: str = "",
) -> Dict[str, Any]:
    cleaned_email = email.lower().strip()
    if not cleaned_email or "@" not in cleaned_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email is required")
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    existing = db.get_user_by_email(cleaned_email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    password_hash = hash_password(password)
    user_id = db.create_user(
        email=cleaned_email,
        password_hash=password_hash,
        name=name or "",
        tier="free",
        provider="email",
    )

    access_token, refresh_token = issue_token_pair(
        user_id=user_id,
        tier="free",
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user = db.get_user_by_id(user_id)
    db.update_last_login(user_id)

    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": JWT_ACCESS_EXPIRE_SECONDS,
    }


def authenticate_user(
    email: str,
    password: str,
    user_agent: str = "",
    ip_address: str = "",
) -> Dict[str, Any]:
    cleaned_email = email.lower().strip()
    user = db.get_user_by_email(cleaned_email)
    if not user or not verify_password(password, user.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
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


def logout_user(
    raw_refresh_token: Optional[str] = None,
    access_token: Optional[str] = None,
) -> None:
    """Revokes refresh token and blocks access token in Redis."""
    if raw_refresh_token:
        try:
            db.revoke_refresh_token(raw_refresh_token)
        except Exception as e:
            logger.debug("Failed to revoke refresh token: %s", e)

    if access_token:
        block_access_token(access_token)


def get_user_profile(user_id: int) -> Dict[str, Any]:
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def migrate_anon_session(anon_id: str, user_id: int) -> None:
    """Copy recent conversation states from an anon identity to user namespace."""
    if not anon_id:
        return
    client = get_redis_client()
    try:
        keys = client.keys(f"tf:session:anon:{anon_id}:*")
        for k in keys:
            session_id = k.split(":")[-1]
            data = client.get(k)
            if data:
                user_key = f"tf:session:user:{user_id}:{session_id}"
                client.set(user_key, data, ex=60 * 60 * 24 * 7)
    except Exception as e:
        logger.debug("Failed migrating anon session to user: %s", e)

