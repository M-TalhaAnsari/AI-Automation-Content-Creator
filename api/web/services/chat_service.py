"""api/web/services/chat_service.py -- Chat orchestration and processing service."""
import logging
import time
from typing import Dict, Any, Optional
from api.web import anon_trial, db
from api.web.handlers import finalize_turn
from orchestration.conversation_agent import process_turn
from memory.redis_session_store import load_conversation, save_conversation

logger = logging.getLogger("trendforge.web.chat_service")
INLINE_ACTIONS = {"add_constraint", "remove_constraint", "clarify", "undo"}


def process_chat_message(
    session_id: str,
    client_name: str,
    message: str,
    platform: Optional[str] = None,
    posts: int = 5,
    verbose: bool = False,
) -> Dict[str, Any]:
    start_time = time.monotonic()
    conversation = load_conversation(session_id, client_name)
    resolved_platform = platform or conversation.get("last_platform")

    routing_start = time.monotonic()
    turn = process_turn(conversation, message)
    routing_ms = int((time.monotonic() - routing_start) * 1000)

    save_conversation(session_id, client_name, conversation)

    if not client_name.startswith("user:"):
        anon_id = client_name.split(":", 1)[1]
        anon_trial.record_message(anon_id, tokens_used=turn.get("tokens_used", 0))

    if client_name.startswith("user:"):
        user_id = int(client_name.split(":", 1)[1])
        title = message[:60] if not conversation.get("last_topic") else None
        try:
            db.upsert_chat_session(user_id, session_id, title=title)
        except Exception as e:
            logger.warning("upsert_chat_session failed for %s/%s: %s", client_name, session_id, e)

    action = turn["action"]
    args = turn.get("args", {})

    total_turn_ms = int((time.monotonic() - start_time) * 1000)
    timings = {
        "routing_ms": routing_ms,
        "total_turn_ms": total_turn_ms,
    }

    if action in INLINE_ACTIONS:
        reply = finalize_turn(action, args, conversation, verbose, prompt=message, platform=resolved_platform, posts=posts)
        save_conversation(session_id, client_name, conversation)
        return {
            "status": "done",
            "session_id": session_id,
            "action": action,
            "reply": reply,
            "tokens_used": turn.get("tokens_used", 0),
            "timings": timings,
        }

    return {
        "status": "processing",
        "session_id": session_id,
        "action": action,
        "args": args,
        "resolved_platform": resolved_platform,
        "tokens_used": turn.get("tokens_used", 0),
        "timings": timings,
    }
