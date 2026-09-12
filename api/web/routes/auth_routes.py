"""api/web/routes/auth_routes.py -- Production-grade Authentication API endpoints."""
import os
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.web import db
from api.web.dependencies.auth_deps import verify_jwt, get_current_user_id
from api.web.schemas import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    TokenPairResponse,
    MeResponse,
    GoogleVerifyRequest,
    GoogleUrlResponse,
)
from api.web.services.auth_service import (
    register_user,
    authenticate_user,
    rotate_refresh_token,
    logout_user,
    get_user_profile,
    migrate_anon_session,
    JWT_REFRESH_EXPIRE_SECONDS,
)
from api.web.services.google_oauth_service import (
    get_google_auth_url,
    exchange_google_code,
    verify_google_id_token,
    provision_google_user,
    verify_and_consume_csrf_state,
    FRONTEND_URL,
)
from api.web.services.tier_service import list_available_plans, get_tier_config

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE_NAME = "trendforge_refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("ENVIRONMENT", "").lower() == "production",
        path="/auth",
        max_age=JWT_REFRESH_EXPIRE_SECONDS,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
    )


# ---------------------------------------------------------------------------
# Email / Password Auth Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
):
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    result = register_user(
        email=body.email,
        password=body.password,
        name=body.name,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, result["refresh_token"])

    # Seamlessly migrate pre-login guest chats into the new account
    if x_anon_id:
        migrate_anon_session(x_anon_id, result["user"]["id"])

    user_data = MeResponse(**result["user"])
    return TokenResponse(
        token=result["access_token"],
        access_token=result["access_token"],
        expires_in=result["expires_in"],
        user=user_data,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
):
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    result = authenticate_user(
        email=body.email,
        password=body.password,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, result["refresh_token"])

    if x_anon_id:
        migrate_anon_session(x_anon_id, result["user"]["id"])

    user_data = MeResponse(**result["user"])
    return TokenResponse(
        token=result["access_token"],
        access_token=result["access_token"],
        expires_in=result["expires_in"],
        user=user_data,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, response: Response):
    """
    Rotates refresh token and issues a new access token.
    Reads refresh token from HttpOnly cookie (or Authorization header fallback).
    """
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        # Check Authorization header as fallback
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            raw_token = auth_hdr[len("Bearer "):]

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token cookie",
        )

    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    result = rotate_refresh_token(
        raw_refresh_token=raw_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, result["refresh_token"])

    user_data = MeResponse(**result["user"])
    return TokenResponse(
        token=result["access_token"],
        access_token=result["access_token"],
        expires_in=result["expires_in"],
        user=user_data,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
):
    """
    Revokes refresh token in database, revokes access token in Redis blocklist,
    and clears HttpOnly refresh cookie.
    """
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    access_token = None
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization[len("Bearer "):].strip()

    logout_user(raw_refresh_token=raw_refresh, access_token=access_token)
    _clear_refresh_cookie(response)
    return {"ok": True, "message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# Google OAuth 2.0 Endpoints
# ---------------------------------------------------------------------------

@router.get("/google/url", response_model=GoogleUrlResponse)
def get_google_login_url():
    """Returns Google OAuth 2.0 consent URL with CSRF protection."""
    data = get_google_auth_url()
    return GoogleUrlResponse(url=data["url"])


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Google OAuth 2.0 Authorization Code callback endpoint.
    Exchanges authorization code, provisions user, and redirects to frontend.
    """
    if error:
        logger_target = f"{FRONTEND_URL}/?google_auth_error={error}"
        return RedirectResponse(url=logger_target)

    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}/?google_auth_error=missing_code")

    # Verify CSRF state
    if not verify_and_consume_csrf_state(state):
        return RedirectResponse(url=f"{FRONTEND_URL}/?google_auth_error=invalid_csrf_state")

    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    profile = await exchange_google_code(code)
    result = provision_google_user(profile, user_agent=user_agent, ip_address=ip_address)

    # Set refresh cookie on redirect
    redirect_resp = RedirectResponse(
        url=f"{FRONTEND_URL}/?google_auth=success&token={result['access_token']}",
        status_code=status.HTTP_302_FOUND,
    )
    _set_refresh_cookie(redirect_resp, result["refresh_token"])
    return redirect_resp


@router.post("/google/verify", response_model=TokenResponse)
async def verify_google_credential(
    body: GoogleVerifyRequest,
    request: Request,
    response: Response,
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
):
    """
    Direct verification for Google Identity Services / One-Tap button.
    Receives Google ID token from frontend, verifies it with Google, and returns session tokens.
    """
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""

    profile = await verify_google_id_token(body.credential)
    result = provision_google_user(profile, user_agent=user_agent, ip_address=ip_address)
    _set_refresh_cookie(response, result["refresh_token"])

    if x_anon_id:
        migrate_anon_session(x_anon_id, result["user"]["id"])

    user_data = MeResponse(**result["user"])
    return TokenResponse(
        token=result["access_token"],
        access_token=result["access_token"],
        expires_in=result["expires_in"],
        user=user_data,
    )


# ---------------------------------------------------------------------------
# User Profile & Tiers
# ---------------------------------------------------------------------------

@router.get("/me", response_model=MeResponse)
def me(client_name: str = Depends(verify_jwt)):
    user_id = get_current_user_id(client_name)
    user = get_user_profile(user_id)
    return MeResponse(**user)


class UpgradeRequest(BaseModel):
    tier: str


@router.get("/plans")
def get_plans():
    """Return available creator and agency plans with model quotas."""
    return {"plans": list_available_plans()}


@router.post("/upgrade")
def upgrade_tier(body: UpgradeRequest, client_name: str = Depends(verify_jwt)):
    """Switch or upgrade user tier."""
    user_id = get_current_user_id(client_name)
    config = get_tier_config(body.tier)
    db.update_user_tier(user_id, config.id)
    return {"ok": True, "tier": config.id, "plan_name": config.name}

