"""
web/schemas.py -- request/response models, kept in their own file so
app.py stays about routing and jobs.py can import the same response
shape without importing FastAPI itself.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    # Optional here on purpose: a browser client can rely on the cookie
    # set by /chat's response; a non-browser client (Slack bot, mobile
    # app, another service) has no cookie jar and must be able to pass
    # session_id explicitly. See web/deps.py for the resolution order.
    session_id: Optional[str] = None
    platform: Optional[str] = None
    posts: int = 5
    verbose: bool = False


class ChatResponse(BaseModel):
    status: str  # "done" | "processing"
    session_id: str
    action: str
    reply: Optional[str] = None
    job_id: Optional[str] = None
    tokens_used: Optional[int] = None


class JobStatusResponse(BaseModel):
    status: str  # "processing" | "done" | "error"
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