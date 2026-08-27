"""api/web/routes/auth_routes.py -- Authentication and User API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from api.web.dependencies.auth_deps import verify_jwt
from api.web.schemas import SignupRequest, LoginRequest, TokenResponse, MeResponse
from api.web.services.auth_service import register_user, authenticate_user, get_user_profile

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest):
    result = register_user(email=body.email, password=body.password, name=body.name)
    return TokenResponse(token=result["token"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    result = authenticate_user(email=body.email, password=body.password)
    return TokenResponse(token=result["token"])


from pydantic import BaseModel
from api.web import db
from api.web.services.tier_service import list_available_plans, get_tier_config


class UpgradeRequest(BaseModel):
    tier: str


@router.get("/plans")
def get_plans():
    """Return available creator and agency plans with model quotas."""
    return {"plans": list_available_plans()}


@router.post("/upgrade")
def upgrade_tier(body: UpgradeRequest, client_name: str = Depends(verify_jwt)):
    """Switch or upgrade user tier."""
    user_id = int(client_name.split(":", 1)[1])
    config = get_tier_config(body.tier)
    db.update_user_tier(user_id, config.id)
    return {"ok": True, "tier": config.id, "plan_name": config.name}


@router.get("/me", response_model=MeResponse)
def me(client_name: str = Depends(verify_jwt)):
    user_id = int(client_name.split(":", 1)[1])
    user = get_user_profile(user_id)
    return MeResponse(**user)
