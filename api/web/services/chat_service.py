"""api/web/services/chat_service.py -- Chat orchestration and processing service."""
import logging
import time
from typing import Dict, Any, Optional
from api.web import anon_trial, db
from api.web.handlers import finalize_turn
from orchestration.conversation_agent import process_turn
from memory.redis_session_store import load_conversation, save_conversation

from api.web.security.owasp_guardrails import sanitize_and_validate_prompt
from api.web.services.cache_service import FAST_MEMORY_CACHE

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
    
    # 1. OWASP Prompt Guardrail Sanitization (LLM01 / LLM02)
    sanitized_message, is_safe, security_warning = sanitize_and_validate_prompt(message)
    
    conversation = load_conversation(session_id, client_name)
    resolved_platform = platform or conversation.get("last_platform")

    # 2. Inject User Brand Memory & Creator Persona (if logged in)
    if client_name.startswith("user:"):
        user_id = int(client_name.split(":", 1)[1])
        cache_key = f"user_prefs:{user_id}"
        prefs = FAST_MEMORY_CACHE.get(cache_key)
        if not prefs:
            try:
                prefs = db.get_user_preferences(user_id)
                FAST_MEMORY_CACHE.set(cache_key, prefs, ttl_sec=120)
            except Exception as e:
                logger.debug("Could not fetch user preferences: %s", e)
                prefs = {}
        if prefs:
            conversation["user_preferences"] = prefs
            conversation["user_brand_memory"] = prefs

    routing_start = time.monotonic()
    turn = process_turn(conversation, sanitized_message)
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
