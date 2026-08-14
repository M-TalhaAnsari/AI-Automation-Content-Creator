"""
orchestration/dispatch.py — Action handlers + dispatch table

Split out of main.py per FLOW.md's migration plan. Contains every
_handle_* function and dispatch_action, unchanged from main.py except:
  - imports `run` from pipeline.generate instead of defining it locally
  - imports process_turn's counterpart tools from orchestration.
    conversation_agent (the renamed conversation/orchestrator.py) where
    relevant -- dispatch_action itself doesn't call process_turn
    directly (that stays in main.py's interactive_mode, which resolves
    the action BEFORE calling dispatch_action), so no change was needed
    here for that rename; it's noted for anyone tracing the call chain.

This is the module api/web/handlers.py should eventually import
(`import orchestration.dispatch as dispatch`) once its own one-line fix
is applied -- see FLOW.md's "Structural work still pending" section.
That file's actual source hasn't been sent yet, so that edit isn't
applied here.
"""

import uuid

from core.state import create_initial_state, add_tokens
from pipeline.generate import run

MAX_ACTIVE_CONSTRAINTS = 20
# Carried over unchanged from main.py -- not referenced anywhere in the
# main.py source seen so far. Kept rather than dropped in case something
# outside the shown files depends on it; flagging rather than silently
# deleting what might be dead code.
MAX_RECENT_MESSAGES = 5

MAX_POST_HISTORY = 3


def _snapshot_posts(conversation):
    """Push the current last_generated_posts onto post_history before it's
    about to be overwritten, so a wrong result is one 'undo' away instead
    of silently gone. Never raises -- a failed snapshot degrades to no
    undo available, not a broken request."""
    current = conversation.get("last_generated_posts")
    if not current:
        return
    history = conversation.setdefault("post_history", [])
    history.append(current)
    conversation["post_history"] = history[-MAX_POST_HISTORY:]


def _handle_undo(args, conversation, verbose):
    history = conversation.get("post_history", [])
    if not history:
        confirmation = "There's nothing to undo — no previous version saved."
        print(f"\n  ℹ️  {confirmation}\n")
        conversation["last_output"] = confirmation
        return
    conversation["last_generated_posts"] = history.pop()
    conversation["post_history"] = history
    count = len(conversation["last_generated_posts"])
    confirmation = f"Reverted to the previous version — {count} post(s) restored."
    print(f"\n  ↩️  {confirmation}\n")
    conversation["last_output"] = confirmation


def _summarize_for_chat(platform: str, topic: str, post_count: int) -> str:
    plural = "s" if post_count != 1 else ""
    topic_part = f' about "{topic}"' if topic else ""
    return f"Generated {post_count} {platform} post{plural}{topic_part}."


def _handle_run_new_request(args, prompt, platform, posts, verbose, conversation):
    resolved_prompt = args.get("prompt") or prompt
    resolved_platform = args.get("platform") or platform
    if verbose and resolved_prompt != prompt:
        print(f"  [Action] using orchestrator-resolved prompt instead of raw input:\n"
              f"           {resolved_prompt!r}")
    result = run(resolved_prompt, platform=resolved_platform, post_count=posts, verbose=verbose)
    _snapshot_posts(conversation)
    conversation["last_topic"] = result.get("topic")
    conversation["last_platform"] = result.get("platform")
    conversation["last_content_intent"] = result.get("content_intent")
    conversation["last_generated_posts"] = result.get("posts", [])
    # FIX (P9): last_output previously held the full terminal-formatted
    # block (state["final_output"] -- box-drawing chars, emoji section
    # headers, meant for a monospace CLI). web/jobs.py's run_slow_action
    # returns this exact field verbatim as the chat reply, so that block
    # was landing straight in the web UI. The CLI's own real-time display
    # is unaffected -- run() already printed state["final_output"] in full
    # before returning, and save_output() still writes the complete block
    # to disk. Only the shared last_output field (used by both the CLI's
    # "last" command and the web reply) changes to something meant to be
    # read in a chat bubble; the structured posts themselves still flow to
    # the frontend separately via last_generated_posts / GET /session.
    conversation["last_output"] = _summarize_for_chat(
        result.get("platform", ""), result.get("topic", ""), len(result.get("posts", [])),
    )


def _handle_generate_more(args, conversation, verbose):
    from generation.platforms.registry import get_platform_strategy
    from generation.content_generator import ContentGenerator
    from generation.formatter import format_output, save_output
    from research.fetchers.fetcher_orchestrator import FetcherOrchestrator

    platform = conversation.get("last_platform") or "instagram"
    base_topic = conversation.get("last_topic") or ""
    content_intent = conversation.get("last_content_intent") or "showcase"
    strategy = get_platform_strategy(platform)
    requested_count = args.get("count") or 1
    topic_delta = (args.get("topic_delta") or "").strip()

    # FIX: previously this always reused base_topic verbatim and had no
    # field at all to carry a refinement -- "give me one more" and "give
    # me project ideas based on these, with github links" produced
    # near-identical output (confirmed in a real run: posts 6-10 were
    # rewordings of posts 1-5, the actual request was silently dropped).
    # effective_topic is what's actually fetched/generated against here;
    # base_topic is deliberately NOT overwritten with it below, so repeated
    # generate_more calls don't compound deltas into an ever-longer topic
    # string turn after turn.
    effective_topic = f"{base_topic} — {topic_delta}" if topic_delta else base_topic

    if verbose:
        print(f"  [Action] generate_more(count={requested_count}, topic_delta={topic_delta!r}, accumulates={strategy.accumulates_posts()})")

    leftover = conversation.get("leftover_fetch_pool", [])
    # A topic_delta changes what's actually relevant to fetch -- the old
    # leftover pool was gathered for the ORIGINAL topic and may not serve
    # a meaningfully different angle, so it's only reused when there's no
    # refinement at all.
    if leftover and not topic_delta:
        regrouped = {}
        for item in leftover:
            regrouped.setdefault(item.get("_source", "leftover"), []).append(item)
        fetched_data = regrouped
    else:
        fetch_state = {
            "core_topic": effective_topic,
            "fetch_summary": effective_topic,
            "search_queries": [effective_topic],
            "content_intent": content_intent,
            "selected_sources": ["github", "tavily", "google_trends", "youtube", "hackernews"],
            "errors": [],
        }
        fetch_result = FetcherOrchestrator().fetch(fetch_state)
        fetched_data = fetch_result.get("fetched_data", {})

    state = create_initial_state(raw_prompt=f"more: {effective_topic}", session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = effective_topic
    state["platform"] = platform
    state["content_intent"] = content_intent
    state["post_count"] = requested_count
    state["post_count_explicit"] = True  # generate_more's count is always a deliberate value
    state["fetched_data"] = fetched_data
    state["total_items_fetched"] = sum(len(v) for v in fetched_data.values())
    state["sources_used"] = list(fetched_data.keys())
    state["active_constraints"] = conversation.get("active_constraints", [])

    state = ContentGenerator().generate(state)
    new_posts = state.get("generated_posts", [])

    if strategy.accumulates_posts():
        # FIX: this is the actual bug fix. run_new_request always
        # OVERWRITES last_generated_posts -- "give me one more" going
        # through that tool silently destroyed the prior post instead of
        # adding to it. This handler appends, and renumbers so post
        # chips / edit-target indices stay consistent with the combined
        # array, not each generation call's own internal 1..N numbering.
        combined = conversation.get("last_generated_posts", []) + new_posts
        for i, p in enumerate(combined, 1):
            p["number"] = i
        conversation["last_generated_posts"] = combined
        conversation["leftover_fetch_pool"] = state.get("leftover_fetch_pool", [])
    else:
        _snapshot_posts(conversation)
        conversation["last_generated_posts"] = new_posts

    state["generated_posts"] = conversation["last_generated_posts"]
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")

    conversation["last_topic"] = base_topic
    conversation["last_platform"] = platform
    conversation["last_content_intent"] = content_intent
    conversation["last_output"] = _summarize_for_chat(platform, base_topic, len(new_posts))


_EDIT_ERROR_MESSAGES = {
    "no_posts_to_edit": "There's nothing generated yet to edit -- try generating some posts first.",
    "no_valid_target_posts": "I couldn't tell which post you meant -- try referring to it by number, or say \"the post\" if there's only one.",
}


def _handle_edit_existing(args, conversation, verbose):
    from conversation.actions import edit_existing
    from generation.formatter import format_output, save_output
    target_posts, instruction = args.get("target_posts", "all"), args.get("instruction", "")
    if verbose:
        print(f"  [Action] edit_existing(target_posts={target_posts!r}, instruction={instruction!r})")
    result = edit_existing(target_posts, instruction, conversation.get("last_generated_posts", []))

    if result.get("error"):
        error_code = result["error"]
        # FIX (production-grade error UX): last_output is the actual chat
        # reply (see P9) -- it must never show a raw internal code like
        # "no_valid_target_posts" verbatim to the user. The CLI print
        # below keeps the real code for debugging; only the conversation-
        # facing message gets translated.
        human_message = _EDIT_ERROR_MESSAGES.get(
            error_code,
            "I couldn't apply that edit -- the post(s) are unchanged. Try rephrasing what you'd like changed.",
        )
        print(f"\n  ⚠️  Couldn't apply that edit ({error_code}) — posts are unchanged.\n")
        conversation["last_output"] = human_message
        return

    _snapshot_posts(conversation)
    conversation["last_generated_posts"] = result["edited_posts"]

    state = create_initial_state(raw_prompt=instruction, session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = conversation.get("last_topic") or ""
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["generated_posts"] = conversation["last_generated_posts"]
    state["sources_used"] = []
    add_tokens(state, "content_generation", result["tokens_used"])
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")
    # FIX (P9): see _handle_run_new_request -- last_output is the chat
    # reply, not the terminal block. state["final_output"] (printed above,
    # saved to disk above) is untouched for CLI users.
    conversation["last_output"] = (
        f'Updated the post(s) — {instruction}' if instruction else "Updated the requested post(s)."
    )


def _handle_add_constraint(args, conversation, verbose):
    from conversation.actions import add_constraint
    ctype, cvalue = args.get("constraint_type", "exclude"), args.get("constraint_value", "")
    result = add_constraint(ctype, cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"][-MAX_ACTIVE_CONSTRAINTS:]
    confirmation = f"✅ Got it — will {ctype} '{cvalue}' going forward."
    print(f"\n  {confirmation}\n")
    conversation["last_output"] = confirmation


def _handle_remove_constraint(args, conversation, verbose):
    from conversation.actions import remove_constraint
    cvalue = args.get("constraint_value", "")
    before = len(conversation.get("active_constraints", []))
    result = remove_constraint(cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"]
    after = len(conversation["active_constraints"])
    confirmation = (f"✅ Removed constraint on '{cvalue}'." if after < before
                    else f"ℹ️  No active constraint matching '{cvalue}' found.")
    print(f"\n  {confirmation}\n")
    conversation["last_output"] = confirmation


def _handle_clarify(args, conversation, verbose):
    question = args.get("clarify_question", "Could you clarify what you'd like me to do?")
    print(f"\n  🤔 {question}\n")
    conversation["last_output"] = question


def _handle_targeted_refetch(args, conversation, verbose):
    from conversation.actions import targeted_refetch
    from generation.content_generator import ContentGenerator
    from generation.formatter import format_output, save_output
    topic_delta = args.get("topic_delta", "")
    current_topic = conversation.get("last_topic") or ""
    refetch_result = targeted_refetch(topic_delta, current_topic,
                                       conversation.get("leftover_fetch_pool", []),
                                       conversation.get("active_constraints", []))
    state = create_initial_state(raw_prompt=f"{current_topic} {topic_delta}".strip(),
                                  session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = f"{current_topic} ({topic_delta})".strip()
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["content_intent"] = conversation.get("last_content_intent") or "showcase"
    state["fetched_data"] = refetch_result["fetched_data"]
    state["total_items_fetched"] = sum(len(v) for v in refetch_result["fetched_data"].values())
    state["sources_used"] = list(refetch_result["fetched_data"].keys())
    state["active_constraints"] = conversation.get("active_constraints", [])
    state = ContentGenerator().generate(state)
    _snapshot_posts(conversation)
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")
    conversation["last_topic"] = state["core_topic"]
    conversation["last_generated_posts"] = state["generated_posts"]
    # FIX (P9): see _handle_run_new_request -- same reasoning.
    conversation["last_output"] = _summarize_for_chat(
        state.get("platform", ""), state.get("core_topic", ""), len(state.get("generated_posts", [])),
    )
    conversation["leftover_fetch_pool"] = state.get("leftover_fetch_pool", [])


def dispatch_action(action, args, conversation, verbose, prompt="", platform=None, posts=5):
    handlers = {
        "run_new_request": lambda: _handle_run_new_request(args, prompt, platform, posts, verbose, conversation),
        "generate_more": lambda: _handle_generate_more(args, conversation, verbose),
        "undo": lambda: _handle_undo(args, conversation, verbose),
        "edit_existing": lambda: _handle_edit_existing(args, conversation, verbose),
        "add_constraint": lambda: _handle_add_constraint(args, conversation, verbose),
        "remove_constraint": lambda: _handle_remove_constraint(args, conversation, verbose),
        "targeted_refetch": lambda: _handle_targeted_refetch(args, conversation, verbose),
        "clarify": lambda: _handle_clarify(args, conversation, verbose),
    }
    fn = handlers.get(action)
    if fn is None:
        print(f"  ⚠️  Unknown action '{action}' — falling back to a fresh request.")
        fn = handlers["run_new_request"]
    fn()