"""api/web/routes/chat_routes.py -- Chat processing API endpoints with Server-Sent Events (SSE)."""
import asyncio
import logging
import os
import time
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from memory.redis_session_store import REDIS_URL
from api.web.dependencies.auth_deps import verify_identity
from api.web.dependencies.session_deps import resolve_session_id
from api.web.dependencies.rate_limit_deps import limiter
from api.web.schemas import ChatRequest, ChatResponse, JobStatusResponse, SseTicketResponse
from api.web.services.chat_service import process_chat_message
from api.web.services.auth_service import verify_access_token
from api.web.services.sse_service import (
    create_sse_ticket,
    verify_sse_ticket,
    publish_sse_event,
    format_sse_message,
    format_sse_heartbeat,
    read_stream_events_batch,
)
from api.web.jobs import run_slow_action
from api.web import anon_trial

logger = logging.getLogger("trendforge.web.chat_routes")
router = APIRouter(prefix="/chat", tags=["Chat"])

_redis_conn = Redis.from_url(REDIS_URL)
_queue = Queue("trendforge", connection=_redis_conn)


@router.get("/ticket", response_model=SseTicketResponse)
def get_sse_ticket(
    stream_key: Optional[str] = Query(None),
    client_name: str = Depends(verify_identity),
):
    """
    Issues a short-lived, single-use SSE ticket for authorizing EventSource connections
    without exposing long-lived access tokens in URL query strings.
    """
    key = stream_key or "default"
    ticket = create_sse_ticket(client_name, key)
    return SseTicketResponse(ticket=ticket, expires_in=60)


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
def send_chat(
    body: ChatRequest,
    request: Request,
    response: Response,
    client_name: str = Depends(verify_identity),
):
    session_id = resolve_session_id(request, response, body.session_id)
    stream_key = body.stream_key or session_id

    result = process_chat_message(
        session_id=session_id,
        client_name=client_name,
        message=body.message,
        platform=body.platform,
        posts=body.posts,
        verbose=body.verbose,
    )

    if result["status"] == "done":
        # Also emit done event on SSE stream for immediate completion
        publish_sse_event(
            stream_key,
            "done",
            {
                "action": result["action"],
                "reply": result.get("reply"),
                "tokens_used": result.get("tokens_used", 0),
            },
        )
        return ChatResponse(
            status="done",
            session_id=session_id,
            action=result["action"],
            reply=result.get("reply"),
            stream_key=stream_key,
            tokens_used=result.get("tokens_used", 0),
            timings=result.get("timings"),
        )

    # Initial pipeline status published to stream
    publish_sse_event(
        stream_key,
        "status",
        {"step": "queued", "message": "Enqueued content generation job..."},
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
        stream_key,
        job_timeout=180,
        result_ttl=3600,
        meta={"client_name": client_name},
    )

    return ChatResponse(
        status="processing",
        session_id=session_id,
        action=result["action"],
        job_id=job.id,
        stream_key=stream_key,
        tokens_used=result.get("tokens_used", 0),
        timings=result.get("timings"),
    )


@router.get("/stream/{stream_key}")
async def stream_chat_events(
    stream_key: str,
    request: Request,
    ticket: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    x_anon_id: Optional[str] = Header(None, alias="X-Anon-Id"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """
    High-availability Server-Sent Events (SSE) stream backed by Redis Streams.
    Supports reconnection with Last-Event-ID header and token or ticket authentication.
    """
    authenticated = False
    client_identity = None

    # 1. Ticket-based authentication (preferred for SSE / EventSource)
    if ticket:
        ticket_data = verify_sse_ticket(ticket, stream_key)
        if ticket_data:
            authenticated = True
            client_identity = ticket_data.get("client_name")

    # 2. Bearer token authentication fallback
    if not authenticated and authorization and authorization.startswith("Bearer "):
        try:
            token = authorization[len("Bearer "):].strip()
            payload = verify_access_token(token)
            authenticated = True
            client_identity = payload.get("sub")
        except Exception:
            pass

    # 3. Anonymous guest fallback
    if not authenticated and x_anon_id:
        authenticated = True
        client_identity = f"anon:{x_anon_id}"

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid SSE ticket or authentication token required",
        )

    async def event_generator():
        cursor = last_event_id or "0-0"
        last_heartbeat = time.time()
        timeout_seconds = 300  # 5 minutes maximum stream duration
        start_time = time.time()

        while True:
            if await request.is_disconnected():
                logger.debug("Client disconnected from SSE stream %s", stream_key)
                break

            if time.time() - start_time > timeout_seconds:
                yield format_sse_message("timeout", "timeout", {"message": "Stream timeout reached"})
                break

            # Read events batch from Redis stream
            events = await asyncio.to_thread(
                read_stream_events_batch,
                stream_key=stream_key,
                last_id=cursor,
                count=50,
                block_ms=2500,
            )

            if events:
                for entry_id, event_type, data in events:
                    cursor = entry_id
                    yield format_sse_message(entry_id, event_type, data)
                    last_heartbeat = time.time()

                    # Terminal events close the stream gracefully
                    if event_type in ("done", "error"):
                        return
            else:
                # Periodic heartbeat comment keeps connection open through firewalls/proxies
                if time.time() - last_heartbeat >= 15:
                    yield format_sse_heartbeat()
                    last_heartbeat = time.time()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
@limiter.limit("60/minute")
def get_chat_job_status(
    request: Request,
    response: Response,
    job_id: str,
    client_name: str = Depends(verify_identity),
):
    """Polling fallback for environments or clients where SSE is unavailable."""
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

