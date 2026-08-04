"""
web/jobs.py -- background job that a worker process (web/worker.py)
actually executes. This is where the 20-96s pipeline runs, off the
request thread.
"""
from typing import Any, Dict, Optional


def run_slow_action(
    session_id: str,
    client_name: str,
    action: str,
    args: Dict[str, Any],
    prompt: str = "",
    platform: Optional[str] = None,
    posts: int = 5,
    verbose: bool = False,
) -> Dict[str, Any]:
    from memory.redis_session_store import load_conversation, save_conversation
    from web.handlers import finalize_turn

    conversation = load_conversation(session_id, client_name)

    reply = finalize_turn(action, args, conversation, verbose, prompt=prompt, platform=platform, posts=posts)

    save_conversation(session_id, client_name, conversation)

    return {
        "action": action,
        "reply": reply,
        "topic": conversation.get("last_topic"),
        "platform": conversation.get("last_platform"),
    }