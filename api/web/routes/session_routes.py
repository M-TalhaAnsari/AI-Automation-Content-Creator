"""api/web/routes/session_routes.py -- Session management API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from api.web.dependencies.auth_deps import verify_identity, verify_jwt
from api.web.schemas import SessionListItem, SessionView
from api.web.services.session_service import get_session_view, delete_session, list_user_sessions
from api.web.dependencies.rate_limit_deps import limiter

router = APIRouter(tags=["Sessions"])


@router.get("/sessions", response_model=List[SessionListItem])
def list_sessions(client_name: str = Depends(verify_jwt)):
    user_id = int(client_name.split(":", 1)[1])
    return [SessionListItem(**row) for row in list_user_sessions(user_id)]


@router.get("/session/{session_id}", response_model=SessionView)
@limiter.limit("60/minute")
def get_session(
    request: Request,
    response: Response,
    session_id: str,
    client_name: str = Depends(verify_identity),
):
    data = get_session_view(session_id, client_name)
    return SessionView(**data)


@router.delete("/session/{session_id}")
def delete_chat_session(
    session_id: str,
    client_name: str = Depends(verify_identity),
):
    delete_session(session_id, client_name)
    return {"status": "deleted", "session_id": session_id}


@router.post("/session/claim-guest")
def claim_guest_session_endpoint(
    body: dict,
    client_name: str = Depends(verify_jwt),
):
    guest_session_id = body.get("guest_session_id")
    if not guest_session_id:
        return {"status": "skipped", "reason": "no_guest_session_id"}
    from memory.redis_session_store import claim_guest_conversation
    ok = claim_guest_conversation(guest_session_id, client_name)
    return {"status": "claimed" if ok else "not_found", "session_id": guest_session_id}
