"""api/web/services/session_service.py -- Conversation session operations."""
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from api.web import db
from memory.redis_session_store import (
    load_conversation,
    save_conversation,
    delete_conversation,
)


def get_session_view(session_id: str, client_name: str) -> Dict[str, Any]:
    conversation = load_conversation(session_id, client_name)
    return {"session_id": session_id, **conversation}


def delete_session(session_id: str, client_name: str) -> bool:
    ok = delete_conversation(session_id, client_name)
    if not ok:
        raise HTTPException(status_code=503, detail="Could not reach session store")
    if client_name.startswith("user:"):
        try:
            user_id = int(client_name.split(":", 1)[1])
            db.delete_chat_session(user_id, session_id)
        except Exception:
            pass
    return True


def list_user_sessions(user_id: int) -> List[Dict[str, Any]]:
    return db.list_chat_sessions(user_id)
