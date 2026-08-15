"""
orchestration/dispatch.py — Action handlers + dispatch table

FIX (this session, four items):
1. targeted_refetch's content_intent is now threaded from the
   conversation's real last_content_intent, not left to actions.py's
   hardcoded default.
2. targeted_refetch now sets state["post_count"]/post_count_explicit --
   previously unset, silently falling back to create_initial_state()'s
   hardcoded 5 regardless of the batch actually being refined.
3. _handle_generate_more's accumulate branch (the default for Instagram/
   TikTok/YouTube/Facebook) now calls _snapshot_posts() before
   overwriting last_generated_posts -- previously missing, meaning
   `undo` after a generate_more on those platforms reverted the wrong
   thing or no-op'd, since the pre-append state was never pushed to
   post_history.
4. Closes the validation-gate gap documented in CLAUDE.md/ARCHITECTURE.md:
   generate_more and targeted_refetch used to call
   ContentGenerator().generate(state) once and return whatever came
   back, with none of run_new_request's retry-until-valid protection.
   New _generate_with_validation() wraps both call sites in a manual
   retry loop using the same gates the graph uses (workflow.gates.
   evaluate_generation_combined) -- decision (a) from CLAUDE.md's two
   options, not routing these actions through the graph itself, since
   their append/leftover-pool semantics don't fit the graph's linear
   format->END assumption without a bigger restructure.
"""

import uuid

from core.state import create_initial_state, add_tokens
from pipeline.generate import run
from Config.config import CONFIG
from workflow.gates import evaluate_generation_combined, MAX_GENERATION_RETRIES

MAX_ACTIVE_CONSTRAINTS = 20
MAX_RECENT_MESSAGES = 5
MAX_POST_HISTORY = 3


def _snapshot_posts(conversation):
    current = conversation.get("last_generated_posts")
    if not current:
        return
    history = conversation.setdefault("post_history", [])
    history.append(current)
    conversation["post_history"] = history[-MAX_POST_HISTORY:]


def _generate_with_validation(state, verbose=False):
    """
    See module docstring, item 4. Not routed through the graph -- a
    manual retry loop calling the same gate function the graph uses.
    """
    from generation.content_generator import ContentGenerator

    original_fetched_data = state.get("fetched_data", {})

    while True:
        # FIX: content_generator.py mutates state["fetched_data"] in
        # place (topic filter, then Pass-1 selection) on every call.
        # Inside the graph this is safe -- state_without_reducer_keys()
        # stops that mutation from persisting between hops, so each
        # graph retry starts from the untouched, reducer-accumulated
        # data again. This loop has no graph and no reducer protecting
        # it, so without this reset, retry 2 would filter/select AGAIN
        # on top of retry 1's already-narrowed output -- silently
        # shrinking the real candidate pool on every retry instead of
        # re-selecting from the full set.
        state["fetched_data"] = {k: list(v) for k, v in original_fetched_data.items()}

        state = ContentGenerator().generate(state)
        result = evaluate_generation_combined(state)
        state["generation_validation_errors"] = result["errors"]

        if result["valid"]:
            if verbose:
                print("  [Action] generation validation passed")
            return state

        if not result["should_retry"]:
            if verbose:
                print(f"  [Action] validation failed after "
                      f"{state.get('generation_retry_count', 0)} retries — "
                      f"proceeding with best-effort output ({len(result['errors'])} issue(s))")
            return state

        state["generation_retry_count"] = state.get("generation_retry_count", 0) + 1
        if verbose:
            print(f"  [Action] validation failed ({len(result['errors'])} issue(s)) — "
                  f"retrying (attempt {state['generation_retry_count']}/{MAX_GENERATION_RETRIES})")


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

    conversation["last_output"] = _summarize_for_chat(
        result.get("platform", ""), result.get("topic", ""), len(result.get("posts", [])),
    )


def _handle_generate_more(args, conversation, verbose):
    from generation.platforms.registry import get_platform_strategy
    from generation.formatter import format_output, save_output
    from research.fetchers.fetcher_orchestrator import FetcherOrchestrator

    platform = conversation.get("last_platform") or "instagram"
    base_topic = conversation.get("last_topic") or ""
    content_intent = conversation.get("last_content_intent") or "showcase"
    strategy = get_platform_strategy(platform)
    requested_count = args.get("count") or 1
    topic_delta = (args.get("topic_delta") or "").strip()

    effective_topic = f"{base_topic} — {topic_delta}" if topic_delta else base_topic

    if verbose:
        print(f"  [Action] generate_more(count={requested_count}, topic_delta={topic_delta!r}, accumulates={strategy.accumulates_posts()})")

    leftover = conversation.get("leftover_fetch_pool", [])

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
    state["post_count_explicit"] = True
    state["fetched_data"] = fetched_data
    state["total_items_fetched"] = sum(len(v) for v in fetched_data.values())
    state["sources_used"] = list(fetched_data.keys())
    state["active_constraints"] = conversation.get("active_constraints", [])

    state = _generate_with_validation(state, verbose)
    new_posts = state.get("generated_posts", [])

    if strategy.accumulates_posts():
        combined = conversation.get("last_generated_posts", []) + new_posts
        for i, p in enumerate(combined, 1):
            p["number"] = i
        _snapshot_posts(conversation)  # FIX: was missing on this branch
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
    from generation.formatter import format_output, save_output
    topic_delta = args.get("topic_delta", "")
    current_topic = conversation.get("last_topic") or ""
    content_intent = conversation.get("last_content_intent") or "showcase"

    refetch_result = targeted_refetch(topic_delta, current_topic,
                                       conversation.get("leftover_fetch_pool", []),
                                       conversation.get("active_constraints", []),
                                       content_intent=content_intent)  # FIX: item 1
    state = create_initial_state(raw_prompt=f"{current_topic} {topic_delta}".strip(),
                                  session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = f"{current_topic} ({topic_delta})".strip()
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["content_intent"] = content_intent

    # FIX: item 2 -- post_count was never set here, silently falling
    # back to create_initial_state()'s hardcoded default of 5 regardless
    # of how many posts were actually being refined. Default to the
    # previous batch size so a targeted refetch doesn't change shape.
    last_posts = conversation.get("last_generated_posts") or []
    state["post_count"] = len(last_posts) if last_posts else CONFIG.system.default_post_count
    state["post_count_explicit"] = True

    state["fetched_data"] = refetch_result["fetched_data"]
    state["total_items_fetched"] = sum(len(v) for v in refetch_result["fetched_data"].values())
    state["sources_used"] = list(refetch_result["fetched_data"].keys())
    state["active_constraints"] = conversation.get("active_constraints", [])

    state = _generate_with_validation(state, verbose)  # FIX: item 4

    _snapshot_posts(conversation)
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")
    conversation["last_topic"] = state["core_topic"]
    conversation["last_generated_posts"] = state["generated_posts"]
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