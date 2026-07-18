"""
web/jobs.py -- background job that a worker process (worker.py) actually
executes. This is where the 20-96s pipeline runs, off the request thread.

Note the import of main.dispatch_action happens INSIDE the job function,
not at module load time -- keeps worker startup fast and avoids importing
the whole pipeline in the web process that only enqueues jobs.
"""
from typing import Any, Dict, Optional


def run_slow_action(
    session_id: str,
    action: str,
    args: Dict[str, Any],
    prompt: str = "",
    platform: Optional[str] = None,
    posts: int = 5,
    verbose: bool = False,
) -> Dict[str, Any]:
    from web.redis_store import get_conversation, save_conversation
    import main

    conversation = get_conversation(session_id)

    main.dispatch_action(
        action, args, conversation, verbose,
        prompt=prompt, platform=platform, posts=posts,
    )

    save_conversation(session_id, conversation)

    return {
        "action": action,
        "reply": conversation.get("last_output", ""),
        "topic": conversation.get("last_topic"),
        "platform": conversation.get("last_platform"),
    }