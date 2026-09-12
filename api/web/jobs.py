"""web/jobs.py -- background job that a worker process (web/worker.py)
actually executes, publishing live SSE pipeline step events to Redis Streams.
"""
import logging
from typing import Any, Dict, Optional

from api.web.services.sse_service import publish_sse_event

logger = logging.getLogger("aiflick.jobs")


def run_slow_action(
    session_id: str,
    client_name: str,
    action: str,
    args: Dict[str, Any],
    prompt: str = "",
    platform: Optional[str] = None,
    posts: int = 5,
    verbose: bool = False,
    stream_key: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    from memory.redis_session_store import load_conversation, save_conversation
    from api.web.handlers import finalize_turn

    # Stream key defaults to session_id if not explicitly provided
    effective_stream_key = stream_key or session_id

    try:
        # Step 1: Researching & analyzing signals
        publish_sse_event(
            effective_stream_key,
            "status",
            {
                "step": "researching",
                "message": "Gathering real-time signals from GitHub, Reddit & HackerNews...",
            },
        )

        conversation = load_conversation(session_id, client_name)

        # Step 2: Generating content
        publish_sse_event(
            effective_stream_key,
            "status",
            {
                "step": "generating",
                "message": f"Composing {posts} viral post variations with Gemini...",
            },
        )

        reply = finalize_turn(
            action,
            args,
            conversation,
            verbose,
            prompt=prompt,
            platform=platform,
            posts=posts,
        )

        save_conversation(session_id, client_name, conversation)

        raw_posts = conversation.get("last_generated_posts", [])

        # Record daily post usage in PostgreSQL for authenticated accounts
        if client_name.startswith("user:") and raw_posts:
            try:
                user_id = int(client_name.split(":", 1)[1])
                from api.web.services.usage_service import record_post_generation
                record_post_generation(user_id, count=len(raw_posts))
            except Exception as usage_err:
                logger.warning("Failed recording daily post usage: %s", usage_err)

        # Step 3: Publish done event with full payload
        publish_sse_event(
            effective_stream_key,
            "done",
            {
                "action": action,
                "reply": reply,
                "topic": conversation.get("last_topic"),
                "platform": conversation.get("last_platform"),
                "posts": raw_posts,
            },
        )

        return {
            "action": action,
            "reply": reply,
            "topic": conversation.get("last_topic"),
            "platform": conversation.get("last_platform"),
        }
    except Exception as e:
        logger.exception("Job execution failed in session %s: %s", session_id, e)
        publish_sse_event(
            effective_stream_key,
            "error",
            {
                "detail": f"Content generation error: {str(e)}",
            },
        )
        raise