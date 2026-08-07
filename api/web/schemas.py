from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    platform: Optional[str] = None
    posts: int = 5
    verbose: bool = False


class ChatResponse(BaseModel):
    status: str
    session_id: str
    action: str
    reply: Optional[str] = None
    job_id: Optional[str] = None
    tokens_used: Optional[int] = None


class JobStatusResponse(BaseModel):
    status: str
    action: Optional[str] = None
    reply: Optional[str] = None
    detail: Optional[str] = None


class SessionView(BaseModel):
    session_id: str
    last_topic: Optional[str] = None
    last_platform: Optional[str] = None
    last_content_intent: Optional[str] = None
    last_generated_posts: List[Dict[str, Any]] = Field(default_factory=list)
    last_output: Optional[str] = None
    active_constraints: List[Dict[str, Any]] = Field(default_factory=list)
    leftover_fetch_pool: List[Dict[str, Any]] = Field(default_factory=list)
    message_history: List[Dict[str, Any]] = Field(default_factory=list)
    rolling_summary: str = ""
    gate_tokens_used: int = 0
    post_history: List[List[Dict[str, Any]]] = Field(default_factory=list)
    pending_confirmation: Optional[Dict[str, Any]] = None


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str


class MeResponse(BaseModel):
    id: int
    email: str


class SessionListItem(BaseModel):
    session_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str