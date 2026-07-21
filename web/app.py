"""
web/app.py -- FastAPI layer wrapping the existing conversation/pipeline
code. Nothing about gate.py, conversation/actions.py, or main.py's
pipeline logic changes here -- this is an adapter, not a rewrite.

Run locally:
    uvicorn web.app:app --reload
Run a worker (separate process, required for run_new_request/
edit_existing/targeted_refetch to ever complete):
    python -m web.worker
"""
import os
import uuid
from typing import Optional

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError

from web.redis_store import get_conversation, save_conversation, REDIS_URL, ping as redis_ping

app = FastAPI(title="TrendForge Conversation API")

_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("trendforge", connection=_redis_conn)

SESSION_COOKIE_NAME = "tf_session_id"
# Actions that are cheap (pure bookkeeping, no pipeline/API calls) run
# inline in the request. Everything else is genuinely slow (per the
# 20-96s pipeline runs in the CLI logs) and must be a background job --
# an HTTP request cannot responsibly block that long.
INLINE_ACTIONS = {"add_constraint", "remove_constraint", "clarify"}


class ChatRequest(BaseModel):
    message: str
    platform: Optional[str] = None
    posts: int = 5
    verbose: bool = False


def _get_or_create_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        session_id = uuid.uuid4().hex
        response.set_cookie(
            SESSION_COOKIE_NAME, session_id,
            httponly=True, samesite="lax", max_age=60 * 60 * 48,
        )
    return session_id


@app.get("/health")
def health():
    return {"ok": True, "redis": redis_ping()}


@app.post("/chat")
def chat(body: ChatRequest, request: Request, response: Response):
    import main  # local import: keeps module import light for workers that don't need the web app

    session_id = _get_or_create_session_id(request, response)
    conversation = get_conversation(session_id)

    platform = body.platform
    if platform is None and conversation.get("last_platform"):
        platform = conversation["last_platform"]

    gate_result = main.resolve_turn(body.message, conversation, verbose=body.verbose)
    # Persist immediately -- recent_messages was just updated by
    # resolve_turn regardless of which action fires below, and if the
    # slow path's job takes a while, we don't want that bookkeeping lost.
    save_conversation(session_id, conversation)

    action = gate_result["action"]
    args = gate_result.get("args", {})

    if action in INLINE_ACTIONS:
        main.dispatch_action(action, args, conversation, body.verbose)
        save_conversation(session_id, conversation)
        return {
            "status": "done",
            "action": action,
            "method": gate_result["method"],
            "reply": conversation.get("last_output", ""),
        }

    job = _queue.enqueue(
        "web.jobs.run_slow_action",
        session_id, action, args, body.message, platform, body.posts, body.verbose,
        job_timeout=180,  # generous vs. the ~96s worst case seen in testing
    )
    return {
        "status": "processing",
        "action": action,
        "method": gate_result["method"],
        "job_id": job.id,
    }


@app.get("/chat/status/{job_id}")
def chat_status(job_id: str):
    try:
        job = Job.fetch(job_id, connection=_redis_conn)
    except NoSuchJobError:
        return {"status": "error", "detail": "unknown or expired job_id"}

    if job.is_finished:
        return {"status": "done", **(job.result or {})}
    if job.is_failed:
        return {"status": "error", "detail": "job failed -- check worker logs"}
    return {"status": "processing"}