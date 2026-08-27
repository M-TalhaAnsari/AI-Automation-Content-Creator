"""api/web/routes/chat_routes.py -- Chat processing API endpoints."""
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from memory.redis_session_store import REDIS_URL
from api.web.dependencies.auth_deps import verify_identity
from api.web.dependencies.session_deps import resolve_session_id
from api.web.dependencies.rate_limit_deps import limiter
from api.web.schemas import ChatRequest, ChatResponse, JobStatusResponse
from api.web.services.chat_service import process_chat_message
from api.web.jobs import run_slow_action
from api.web import anon_trial

logger = logging.getLogger("trendforge.web.chat_routes")
router = APIRouter(prefix="/chat", tags=["Chat"])

_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("trendforge", connection=_redis_conn)


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
def send_chat(
    body: ChatRequest,
    request: Request,
    response: Response,
    client_name: str = Depends(verify_identity),
):
    session_id = resolve_session_id(request, response, body.session_id)
    result = process_chat_message(
        session_id=session_id,
        client_name=client_name,
        message=body.message,
        platform=body.platform,
        posts=body.posts,
        verbose=body.verbose,
    )

    if result["status"] == "done":
        return ChatResponse(
            status="done",
            session_id=session_id,
            action=result["action"],
            reply=result.get("reply"),
            tokens_used=result.get("tokens_used", 0),
            timings=result.get("timings"),
        )

    job = _queue.enqueue(
        run_slow_action,
        session_id,
        client_name,
        result["action"],
        result["args"],
        body.message,
        result["resolved_platform"],
        body.posts,
        body.verbose,
        job_timeout=180,
        result_ttl=3600,
        meta={"client_name": client_name},
    )

    return ChatResponse(
        status="processing",
        session_id=session_id,
        action=result["action"],
        job_id=job.id,
        tokens_used=result.get("tokens_used", 0),
        timings=result.get("timings"),
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
@limiter.limit("60/minute")
def get_chat_job_status(
    request: Request,
    response: Response,
    job_id: str,
    client_name: str = Depends(verify_identity),
):
    try:
        job = Job.fetch(job_id, connection=_redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    if job.meta.get("client_name") != client_name:
        raise HTTPException(status_code=404, detail="unknown or expired job_id")

    if job.is_finished:
        result = job.result or {}
        if not client_name.startswith("user:"):
            anon_id = client_name.split(":", 1)[1]
            anon_trial.add_tokens(anon_id, result.get("tokens_used", 0))
        return JobStatusResponse(
            status="done",
            action=result.get("action"),
            reply=result.get("reply"),
            timings=result.get("timings"),
        )
    if job.is_failed:
        return JobStatusResponse(status="error", detail="job failed -- check worker logs")
    return JobStatusResponse(status="processing")
