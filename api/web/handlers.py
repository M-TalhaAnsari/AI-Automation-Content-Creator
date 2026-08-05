"""
web/handlers.py

The master doc's original plan called for a full parallel set of
web_handle_* functions mirroring main.py's _handle_* functions,
differing only in "return a string" vs "print a string". Building those
would mean re-describing every branch of _handle_edit_existing,
_handle_targeted_refetch, etc. a second time -- exactly the duplication
risk the master doc itself warns about elsewhere ("Zero duplication of
run(), orchestrator.process_turn, or any action's logic").

Every one of main.py's _handle_* functions already writes its result into
conversation["last_output"] AND prints it -- the print is a side effect
the web layer just ignores (it lands in the server/worker process log,
which is fine and arguably useful). So the web layer doesn't need its own
copy of that logic at all: it can call main.dispatch_action directly and
read conversation["last_output"] afterward. That's what this module does,
plus the two follow-up steps interactive_mode() also performs after
dispatch (update_last_tool_result, maybe_summarize) which the original
draft was missing -- without them, web sessions would never get their
tool-call placeholder replaced with the real outcome, and long web
conversations would never get summarized, silently losing early context
exactly like the CLI guards against.
"""
from typing import Any, Dict, Optional

import main
from conversation.orchestrator import maybe_summarize, update_last_tool_result


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
    main.dispatch_action(action, args, conversation, verbose, prompt=prompt, platform=platform, posts=posts)
    update_last_tool_result(conversation, conversation.get("last_output") or "")
    maybe_summarize(conversation)
    return conversation.get("last_output") or ""