from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TimingMeta(BaseModel):
    research_ms: Optional[int] = None
    routing_ms: Optional[int] = None
    generation_ms: Optional[int] = None
    total_turn_ms: Optional[int] = None


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
    timings: Optional[TimingMeta] = None


class JobStatusResponse(BaseModel):
    status: str
    action: Optional[str] = None
    reply: Optional[str] = None
    detail: Optional[str] = None
    timings: Optional[TimingMeta] = None


class SessionView(BaseModel):
    session_id: str
    last_topic: Optional[str] = None
    last_platform: Optional[str] = None
    last_content_intent: Optional[str] = None
    last_generated_posts: List[Any] = Field(default_factory=list)
    last_output: Optional[str] = None
    active_constraints: List[Any] = Field(default_factory=list)
    leftover_fetch_pool: List[Any] = Field(default_factory=list)
    message_history: List[Any] = Field(default_factory=list)
    rolling_summary: Optional[str] = ""
    gate_tokens_used: Optional[int] = 0
    post_history: List[Any] = Field(default_factory=list)
    pending_confirmation: Optional[Any] = None
    last_timings: Optional[Dict[str, Any]] = None


class SignupRequest(BaseModel):
    name: Optional[str] = ""
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str


class MeResponse(BaseModel):
    id: int
    name: Optional[str] = ""
    email: str
    tier: Optional[str] = "free"


class SessionListItem(BaseModel):
    session_id: str
    title: Optional[str] = None
    created_at: str
    last_active_at: str
