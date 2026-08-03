import logging
import uuid
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError

from conversation.orchestrator import process_turn
from memory.redis_session_store import (
    REDIS_URL,
    delete_conversation,
    load_conversation,
    ping as redis_ping,
    save_conversation,
)
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from web.auth import create_jwt, hash_password, verify_jwt, verify_password
from web.db import (
    create_user,
    delete_chat_session,
    get_user_by_email,
    get_user_by_id,
    init_db,
    list_chat_sessions,
    upsert_chat_session,
)
from web.deps import resolve_session_id
from web.handlers import finalize_turn
from web.rate_limit import limiter, rate_limit_exceeded_handler
from web.schemas import (
    ChatRequest,
    ChatResponse,
    JobStatusResponse,
    LoginRequest,
    MeResponse,
    SessionListItem,
    SessionView,
    SignupRequest,
    TokenResponse,
)

logger = logging.getLogger("trendforge.web.app")

app = FastAPI(title="TrendForge Conversation API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("trendforge", connection=_redis_conn)

INLINE_ACTIONS = {"add_constraint", "remove_constraint", "clarify"}


@app.on_event("startup")
def _startup():
    try:
        init_db()
    except Exception as e:
        logger.error("init_db() failed at startup: %s", e)


def _user_id(client_name: str) -> int:
    return int(client_name.split(":", 1)[1])


@app.get("/health")
def health():
    return {"ok": True, "redis": redis_ping()}


@app.post("/auth/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest):
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    password_hash = hash_password(body.password)
    user_id = create_user(body.email, password_hash)
    return TokenResponse(token=create_jwt(user_id))


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(token=create_jwt(user["id"]))


@app.get("/auth/me", response_model=MeResponse)
def me(client_name: str = Depends(verify_jwt)):
    user = get_user_by_id(_user_id(client_name))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return MeResponse(**user)


@app.get("/sessions", response_model=List[SessionListItem])
def sessions(client_name: str = Depends(verify_jwt)):
    return [SessionListItem(**row) for row in list_chat_sessions(_user_id(client_name))]


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
def chat(body: ChatRequest, request: Request, response: Response, client_name: str = Depends(verify_jwt)):
    session_id = resolve_session_id(request, response, body.session_id)
    conversation = load_conversation(session_id, client_name)

    platform = body.platform or conversation.get("last_platform")

    turn = process_turn(conversation, body.message)
    save_conversation(session_id, client_name, conversation)

    title = body.message[:60] if not conversation.get("last_topic") else None
    try:
        upsert_chat_session(_user_id(client_name), session_id, title=title)
    except Exception as e:
        logger.warning("upsert_chat_session failed for %s/%s: %s", client_name, session_id, e)

    action = turn["action"]
    args = turn.get("args", {})

    if action in INLINE_ACTIONS:
        reply = finalize_turn(action, args, conversation, body.verbose, prompt=body.message, platform=platform, posts=body.posts)
        save_conversation(session_id, client_name, conversation)
        return ChatResponse(
            status="done",
            session_id=session_id,
            action=action,
            reply=reply,
            tokens_used=turn.get("tokens_used", 0),
        )

    job = _queue.enqueue(
        "web.jobs.run_slow_action",
        session_id, client_name, action, args, body.message, platform, body.posts, body.verbose,
        job_timeout=180,
        result_ttl=3600,
        meta={"client_name": client_name},
    )
    return ChatResponse(
        status="processing",
        session_id=session_id,
        action=action,
        job_id=job.id,
        tokens_used=turn.get("tokens_used", 0),
    )


@app.get("/chat/status/{job_id}", response_model=JobStatusResponse)
@limiter.limit("60/minute")
def chat_status(request: Request, response: Response, job_id: str, client_name: str = Depends(verify_jwt)):
    try:
        job = Job.fetch(job_id, connection=_redis_conn)
        job.refresh()
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    if job.meta.get("client_name") != client_name:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    if job.is_finished:
        result = job.result or {}
        return JobStatusResponse(status="done", action=result.get("action"), reply=result.get("reply"))
    if job.is_failed:
        return JobStatusResponse(status="error", detail="job failed -- check worker logs")
    return JobStatusResponse(status="processing")


@app.get("/session/{session_id}", response_model=SessionView)
@limiter.limit("60/minute")
def get_session(request: Request, response: Response, session_id: str, client_name: str = Depends(verify_jwt)):
    conversation = load_conversation(session_id, client_name)
    return SessionView(session_id=session_id, **conversation)


@app.delete("/session/{session_id}")
def reset_session(session_id: str, client_name: str = Depends(verify_jwt)):
    ok = delete_conversation(session_id, client_name)
    if not ok:
        raise HTTPException(status_code=503, detail="could not reach session store")
    try:
        delete_chat_session(_user_id(client_name), session_id)
    except Exception as e:
        logger.warning("delete_chat_session failed for %s/%s: %s", client_name, session_id, e)
    return {"status": "deleted", "session_id": session_id}