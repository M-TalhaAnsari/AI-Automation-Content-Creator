
from typing import Any, Dict, Optional

import orchestration.dispatch as dispatch
from orchestration.conversation_agent import maybe_summarize, update_last_tool_result


def finalize_turn(
    action: str,
    args: Dict[str, Any],
    conversation: Dict[str, Any],
    verbose: bool,
    prompt: str = "",
    platform: Optional[str] = None,
    posts: int = 5,
) -> str:
    """Runs the actual action, then the same two housekeeping steps
    interactive_mode() runs after every dispatch. Mutates `conversation`
    in place. Returns the reply string the caller should send back."""
    dispatch.dispatch_action(action, args, conversation, verbose, prompt=prompt, platform=platform, posts=posts)
    update_last_tool_result(conversation, conversation.get("last_output") or "")
    maybe_summarize(conversation)
    return conversation.get("last_output") or ""