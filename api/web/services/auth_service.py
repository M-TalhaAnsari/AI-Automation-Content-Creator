"""api/web/services/auth_service.py -- Authentication, user creation and JWT management service."""
import os
import secrets
import time
from typing import Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

import bcrypt
import jwt
from fastapi import HTTPException
from api.web import db

JWT_SECRET = os.environ.get("JWT_SECRET", "trendforge_default_secret_key_change_in_prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 60 * 60 * 24 * 30  # 30 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_jwt_token(user_id: int) -> str:
    payload = {"sub": f"user:{user_id}", "exp": int(time.time()) + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def register_user(email: str, password: str, name: Optional[str] = "") -> Dict[str, Any]:
    existing = db.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    password_hash = hash_password(password)
    user_id = db.create_user(email=email, password_hash=password_hash, name=name)
    token = create_jwt_token(user_id)
    return {"user_id": user_id, "token": token}


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_jwt_token(user["id"])
    return {"user_id": user["id"], "token": token, "user": user}


def get_user_profile(user_id: int) -> Dict[str, Any]:
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
