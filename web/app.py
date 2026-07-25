"""
web/app.py -- FastAPI layer wrapping the existing conversation/pipeline
code. Nothing about orchestrator.py, conversation/actions.py, or main.py's
pipeline logic changes here -- this is an adapter, not a rewrite.

Run locally:
    uvicorn web.app:app --reload
Run a worker (separate process, required for run_new_request/
edit_existing/targeted_refetch to ever complete):
    python -m web.worker

Bugs fixed vs. the earlier draft (flagged, not silently patched):
  - main.resolve_turn doesn't exist -- process_turn lives in
    conversation/orchestrator.py, per main.py's own interactive_mode().
    This was the exact stale-reference bug the Phase 3 master doc warned
    about ("confirmed stale, calls main.resolve_turn which no longer
    exists post-pivot") -- the new web layer re-introduced it.
  - process_turn returns {action, args, tokens_used, error} -- there is
    no "method" key. The draft read gate_result["method"] in both
    response paths, which would KeyError on the very first request.
  - update_last_tool_result / maybe_summarize were never called after
    dispatch_action -- added in web/handlers.py, see that file's
    docstring for why this matters.
"""
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
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
from web.auth import verify_api_key
from web.deps import resolve_session_id
from web.handlers import finalize_turn
from web.schemas import ChatRequest, ChatResponse, JobStatusResponse, SessionView

app = FastAPI(title="TrendForge Conversation API")

_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("trendforge", connection=_redis_conn)

# Actions that are cheap (pure bookkeeping, no pipeline/LLM/network calls)
# run inline in the request. Everything else is genuinely slow (20-96s
# pipeline runs observed in CLI testing) and must be a background job --
# an HTTP request has no business blocking that long.
INLINE_ACTIONS = {"add_constraint", "remove_constraint", "clarify"}


@app.get("/health")
def health():
    return {"ok": True, "redis": redis_ping()}


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, response: Response, client_name: str = Depends(verify_api_key)):
    session_id = resolve_session_id(request, response, body.session_id)
    conversation = load_conversation(session_id, client_name)

    platform = body.platform or conversation.get("last_platform")

    turn = process_turn(conversation, body.message)
    # Persist immediately -- process_turn already appended to
    # message_history regardless of which action fires next, and if the
    # slow path's job takes a while, that bookkeeping shouldn't be lost
    # if the process restarts in between.
    save_conversation(session_id, client_name, conversation)

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
        job_timeout=180,      # generous vs. the ~96s worst case seen in testing
        result_ttl=3600,      # RQ's default is 500s -- too short for a client that
                              # polls slowly or reconnects later. The underlying
                              # conversation state is safe regardless (it's saved to
                              # Redis under the session's own TTL, independent of this)
                              # -- this only affects how long /chat/status/{job_id}
                              # itself stays answerable.
        meta={"client_name": client_name},  # so /chat/status can verify ownership
    )
    return ChatResponse(
        status="processing",
        session_id=session_id,
        action=action,
        job_id=job.id,
        tokens_used=turn.get("tokens_used", 0),
    )


@app.get("/chat/status/{job_id}", response_model=JobStatusResponse)
def chat_status(job_id: str, client_name: str = Depends(verify_api_key)):
    try:
        job = Job.fetch(job_id, connection=_redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    # A job belongs to whichever client enqueued it (see meta= in /chat
    # above). A different client asking about this job_id gets the exact
    # same 404 as a genuinely nonexistent job -- same no-leak principle
    # as session scoping: don't reveal that a job_id exists for someone
    # else. UUIDs are high-entropy, so this is defense in depth rather
    # than the primary protection, but it costs nothing to check.
    if job.meta.get("client_name") != client_name:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    if job.is_finished:
        result = job.result or {}
        return JobStatusResponse(status="done", action=result.get("action"), reply=result.get("reply"))
    if job.is_failed:
        return JobStatusResponse(status="error", detail="job failed -- check worker logs")
    return JobStatusResponse(status="processing")


@app.get("/session/{session_id}", response_model=SessionView)
def get_session(session_id: str, client_name: str = Depends(verify_api_key)):
    conversation = load_conversation(session_id, client_name)
    return SessionView(session_id=session_id, **conversation)


@app.delete("/session/{session_id}")
def reset_session(session_id: str, client_name: str = Depends(verify_api_key)):
    ok = delete_conversation(session_id, client_name)
    if not ok:
        raise HTTPException(status_code=503, detail="could not reach session store")
    return {"status": "deleted", "session_id": session_id}