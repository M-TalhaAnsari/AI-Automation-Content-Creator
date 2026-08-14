"""
orchestration/conversation_agent.py — Native Tool-Calling Turn Resolver

Renamed from conversation/orchestrator.py per agents/08_conversation_agent.md.
Tool-calling mechanism (native Groq tool-calling, fixed TOOLS schema,
tool_choice="auto") is unchanged per that spec -- it was already
correctly designed. What changed is the confirmation-gate wiring.

FIX (agents/08, safety bug -- ARCHITECTURE.md §8 / CLAUDE.md "still
highest priority, not started"): every return in process_turn now flows
through exactly one of two chokepoints, and nothing else in this file is
allowed to hand back a bare {"action": ..., ...} dict:

  - _resolve(action_name, args, conversation, tokens_used, error) is the
    ONLY place allowed to hand back a concrete action when there is no
    confirmation already in flight. It unconditionally re-checks
    "is this destructive and are there posts to lose" before returning.
  - _ask_reconfirm(...) is used only when a confirmation was ALREADY
    pending and this turn's resolution was ambiguous or failed -- it
    never proceeds to execute anything, only re-asks.
  - The pending-confirmation success branch inside the try block is the
    one deliberate exception: it executes the ORIGINALLY STORED
    action/args deterministically without re-running the gate, because
    the gate already ran on the turn that SET pending_confirmation.
    Re-gating here would just re-ask the same question forever.

Previously, three exit points built the `fallback` dict (defaulting to
run_new_request) directly and returned it WITHOUT checking
DESTRUCTIVE_ACTIONS at all:
  1. the LLM returned no tool_calls and no confirmation was pending
  2. the LLM returned a malformed/unknown tool call
  3. the Groq API call raised an exception
All three are real, reachable paths -- a model can decline to call a
tool, hallucinate a bad tool name, or the API call can simply fail -- and
all three used to fall straight to run_new_request even when
last_generated_posts was non-empty, silently destroying existing content
with no confirmation. Fixed by routing every one of them through
_resolve() or _ask_reconfirm() instead of constructing `fallback` inline.
"""

import json
from Config.config import CONFIG

SYSTEM_PROMPT = (
    "You are TrendForge's conversation assistant. The user is generating "
    "social media content. Decide, for each message, whether to call a "
    "tool to modify/refine existing content or preferences, call "
    "generate_more for ADDITIONAL content on the SAME topic as what's "
    "already been generated, or call run_new_request for a fresh, "
    "genuinely UNRELATED content request. Phrases like 'one more', "
    "'give me another', 'a few more of these' mean generate_more, not "
    "run_new_request. If genuinely uncertain what the user wants, call "
    "clarify and ask — do not guess at destructive or content-altering "
    "actions."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "run_new_request",
        "description": "Generate fresh content for a new topic/platform request.",
        "parameters": {"type": "object", "properties": {
            "prompt": {"type": "string"},
            "platform": {"type": "string", "enum": ["instagram", "youtube", "tiktok", "linkedin", "facebook"]},
        }, "required": ["prompt"]},
    }},
    {"type": "function", "function": {
        "name": "generate_more",
        "description": "User wants ADDITIONAL post(s) on the SAME general topic as what's "
                        "already been generated -- adds to the existing set rather than "
                        "replacing it. Use for 'one more', 'give me another', 'a few more "
                        "of these'. If the user ALSO asks for a different angle, format, "
                        "or specific type of content (e.g. 'give me project ideas based "
                        "on these', 'with github links this time', 'make them shorter'), "
                        "capture that in topic_delta -- never silently ignore it. Do NOT "
                        "use run_new_request for this -- that tool is only for a "
                        "genuinely different, unrelated topic.",
        "parameters": {"type": "object", "properties": {
            "count": {"type": "integer", "description": "How many additional posts. Default 1 if not specified."},
            "topic_delta": {"type": "string", "description": "Any refinement, new angle, "
                            "or specific instruction for these additional posts, beyond "
                            "just 'more of the same' -- e.g. 'project ideas that "
                            "implement these strategies, with github links'. Empty "
                            "string if truly just more of the exact same thing."},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "edit_existing",
        "description": "Modify wording, tone, or length of already-generated posts.",
        "parameters": {"type": "object", "properties": {
            "target_posts": {
                "type": "array", "items": {"type": "integer"},
                "description": "1-based post numbers to target. Omit this field "
                                "entirely if the user means ALL current posts.",
            },
            "instruction": {"type": "string"},
        }, "required": ["instruction"]},
    }},
    {"type": "function", "function": {
        "name": "add_constraint",
        "description": "Remember a standing exclude/prefer preference for the rest of the session.",
        "parameters": {"type": "object", "properties": {
            "constraint_type": {"type": "string", "enum": ["exclude", "prefer"]},
            "constraint_value": {"type": "string"},
        }, "required": ["constraint_type", "constraint_value"]},
    }},
    {"type": "function", "function": {
        "name": "remove_constraint",
        "description": "Undo a previously added exclude/prefer constraint.",
        "parameters": {"type": "object", "properties": {
            "constraint_value": {"type": "string"},
        }, "required": ["constraint_value"]},
    }},
    {"type": "function", "function": {
        "name": "targeted_refetch",
        "description": "User wants broader/narrower/different underlying source data, not just a rewrite.",
        "parameters": {"type": "object", "properties": {
            "topic_delta": {"type": "string"},
        }, "required": ["topic_delta"]},
    }},
    {"type": "function", "function": {
        "name": "undo",
        "description": "User wants to REVERT the most recent post generation or edit, "
                        "restoring the version before that change. Use for 'undo', 'go "
                        "back', 'that's wrong, revert it', 'put it back the way it was'.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "clarify",
        "description": "The request is too ambiguous to act on safely. Ask the user a specific question instead of guessing.",
        "parameters": {"type": "object", "properties": {
            "clarify_question": {"type": "string"},
        }, "required": ["clarify_question"]},
    }},
]

VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

# Unconditional, no exceptions, no pattern matching: any action in this
# set that would replace non-empty last_generated_posts always requires
# one confirmation turn first. Deliberately NOT trying to detect "is this
# specific request actually safe" via keywords/phrasing -- that's the
# exact kind of pattern list that grows forever and still gets bypassed.
# generate_more is deliberately excluded: it's a targeted, contextually-
# informed action (the user already saw this platform's repeat-request
# behavior in context before asking), unlike run_new_request's blind
# unrelated-topic replace.
DESTRUCTIVE_ACTIONS = {"run_new_request"}

SLIDING_WINDOW_TURNS = 20
MAX_HISTORY_TOKENS = 6000


def _rough_tokens(messages) -> int:
    try:
        return sum(len(str(m.get("content", ""))) for m in messages) // 4
    except Exception:
        return 0


def _build_context_messages(conversation: dict, pending_confirmation: dict = None) -> list:
    try:
        history = conversation.get("message_history", [])
        windowed = history[-SLIDING_WINDOW_TURNS:]

        system_content = SYSTEM_PROMPT

        if pending_confirmation:
            # Fixed-size, always identical -- this does not grow as new
            # edge cases show up. The LLM's only job this turn is a
            # narrow yes/no judgment; it does not decide what actually
            # executes (see process_turn -- the stored original action/
            # args are used deterministically, never re-derived).
            system_content += (
                "\n\nThe user was just asked to confirm replacing their existing posts. "
                "If their reply clearly agrees, call run_new_request. If they decline, "
                "ask something else, or seem unsure, call clarify instead — do not guess "
                "in favor of proceeding."
            )

        summary = conversation.get("rolling_summary", "")
        if summary:
            system_content += f"\n\nEARLIER CONVERSATION SUMMARY:\n{summary}"

        posts = conversation.get("last_generated_posts") or []
        if posts:
            titles = "\n".join(f"{i}. {p.get('title', '(untitled)')}" for i, p in enumerate(posts, 1))
            # Every platform answers for itself via its own strategy --
            # this file never checks a platform name directly, so a new
            # platform's "one more" behavior needs zero changes here.
            behavior_note = ""
            last_platform = conversation.get("last_platform")
            if last_platform:
                try:
                    from generation.platforms.registry import get_platform_strategy
                    behavior_note = f" ({get_platform_strategy(last_platform).repeat_request_note()})"
                except Exception:
                    behavior_note = ""
            system_content += f"\n\nCURRENTLY GENERATED POSTS ({len(posts)} total){behavior_note}:\n{titles}"

        constraints = conversation.get("active_constraints", [])
        if constraints:
            c_str = ", ".join(f"{c.get('type','exclude')}:{c.get('value','')}" for c in constraints)
            system_content += f"\n\nACTIVE STANDING CONSTRAINTS: {c_str}"

        messages = [{"role": "system", "content": system_content}] + windowed
        if _rough_tokens(messages) > MAX_HISTORY_TOKENS:
            windowed = windowed[-max(4, SLIDING_WINDOW_TURNS // 2):]
            messages = [{"role": "system", "content": system_content}] + windowed
        return messages
    except Exception:
        return [{"role": "system", "content": SYSTEM_PROMPT}]


def maybe_summarize(conversation: dict) -> None:
    history = conversation.get("message_history", [])
    if len(history) <= SLIDING_WINDOW_TURNS:
        return
    overflow = history[:-SLIDING_WINDOW_TURNS]
    retained = history[-SLIDING_WINDOW_TURNS:]
    if not overflow:
        return
    try:
        from groq import Groq
        client = Groq(api_key=CONFIG.models.groq_api_key)
        overflow_text = "\n".join(
            f"{m.get('role','?')}: {str(m.get('content',''))[:300]}" for m in overflow if m.get("content")
        )
        prior = f"Previous summary: {conversation.get('rolling_summary','')}\n\n" if conversation.get("rolling_summary") else ""
        response = client.chat.completions.create(
            model=CONFIG.models.groq_model_small,
            temperature=0.2, max_tokens=600,
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": "Summarize this conversation segment in 2-4 sentences. "
                 "Focus on topic changes, standing preferences, and what content was generated."},
                {"role": "user", "content": f"{prior}New segment to fold in:\n{overflow_text}"},
            ],
        )
        new_summary = (response.choices[0].message.content or "").strip()
        if new_summary:
            conversation["rolling_summary"] = new_summary
            conversation["message_history"] = retained
    except Exception:
        pass


def update_last_tool_result(conversation: dict, summary: str) -> None:
    history = conversation.get("message_history", [])
    for msg in reversed(history):
        if msg.get("role") == "tool":
            msg["content"] = (summary or "")[:500]
            return


def _resolve(action_name: str, args: dict, conversation: dict, tokens_used: int, error: str = None) -> dict:
    """
    The single chokepoint for every NON-PENDING resolution in
    process_turn. Applies the destructive-action confirmation gate
    unconditionally -- this is the only function in the file allowed to
    hand back a concrete action when there was no confirmation already
    in flight, so a future new failure branch can't quietly bypass the
    gate by building its own return dict inline the way the old
    `fallback` did.

    If action_name is destructive (currently just run_new_request) and
    there are existing posts that would be lost, this converts the
    return into a "clarify" asking for confirmation and stashes
    pending_confirmation instead of letting the action through.
    """
    posts = conversation.get("last_generated_posts")
    if action_name in DESTRUCTIVE_ACTIONS and posts:
        count = len(posts)
        conversation["pending_confirmation"] = {"action": action_name, "args": args}
        question = (
            f"This will replace your {count} existing post(s) with new content — "
            f"reply to confirm, or tell me if you meant something else."
        )
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": question})
        return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": tokens_used, "error": error}
    return {"action": action_name, "args": args, "tokens_used": tokens_used, "error": error}


def _ask_reconfirm(conversation: dict, tokens_used: int, question: str = None, error: str = None) -> dict:
    """
    Used only when a confirmation was ALREADY pending and this turn's
    resolution was ambiguous or failed -- no tool call, an invalid tool
    call, or an exception mid-call. Never proceeds to execute anything,
    only re-asks. Distinct from _resolve(): there's nothing to gate here,
    the gate already fired on the turn that set pending_confirmation.
    """
    conversation.pop("pending_confirmation", None)
    question = question or "Just to confirm — did you want me to go ahead and replace the existing posts?"
    conversation.setdefault("message_history", []).append({"role": "assistant", "content": question})
    return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": tokens_used, "error": error}


def process_turn(conversation: dict, user_message: str) -> dict:
    conversation.setdefault("message_history", []).append({"role": "user", "content": user_message})

    fallback_args = {"prompt": user_message, "platform": conversation.get("last_platform")}

    if not conversation.get("last_generated_posts"):
        # Nothing to lose -- _resolve() will pass this straight through
        # unchanged (the gate only fires when posts is non-empty), but
        # routing it through _resolve() anyway keeps this file to one
        # rule with no carve-outs: every return is built by _resolve()
        # or _ask_reconfirm(), never inline.
        return _resolve("run_new_request", fallback_args, conversation, 0)

    pending = conversation.get("pending_confirmation")

    try:
        from groq import Groq
        client = Groq(api_key=CONFIG.models.groq_api_key)
        messages = _build_context_messages(conversation, pending_confirmation=pending)

        response = client.chat.completions.create(
            model=CONFIG.models.groq_model_large,
            temperature=0.0,
            reasoning_effort="low",
            tools=TOOLS,
            tool_choice="auto",
            messages=messages,
        )
        tokens_used = getattr(response.usage, "total_tokens", 0) if response.usage else 0
        choice = response.choices[0].message
        tool_calls = getattr(choice, "tool_calls", None)

        if not tool_calls:
            conversation["message_history"].append({"role": "assistant", "content": choice.content or ""})
            if pending:
                # No tool call at all during a pending confirmation is
                # ambiguous -- ask again, never guess.
                return _ask_reconfirm(conversation, tokens_used)
            # FIX (bug path #1): previously `return fallback` here,
            # bypassing the gate unconditionally even with posts present.
            return _resolve("run_new_request", fallback_args, conversation, tokens_used)

        call = tool_calls[0]
        conversation["message_history"].append({
            "role": "assistant", "content": choice.content or "",
            "tool_calls": [{"id": call.id, "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments}}],
        })

        action_name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except Exception:
            args = {}

        if action_name not in VALID_TOOL_NAMES or not isinstance(args, dict):
            error = f"Invalid tool call: {action_name!r} / {args!r}"
            if pending:
                # Same reasoning as the no-tool-calls branch: a malformed
                # call during a pending confirmation is not an
                # affirmative answer, so ask again instead of guessing.
                return _ask_reconfirm(conversation, tokens_used, error=error)
            # FIX (bug path #2): previously `return fallback` here too --
            # the second confirmed bypass.
            return _resolve("run_new_request", fallback_args, conversation, tokens_used, error=error)

        conversation["message_history"].append({
            "role": "tool", "tool_call_id": call.id, "content": f"dispatched:{action_name}",
        })

        if pending:
            # Resolving a pending confirmation: the LLM's only job this
            # turn was the narrow affirm-vs-decline judgment. A "clarify"
            # call means decline/unsure. Anything else means proceed --
            # and we execute the ORIGINALLY STORED action/args
            # deterministically, never a freshly re-derived call, so
            # confirming can never silently change what actually runs.
            # This is the one deliberate place that hands back a
            # destructive action without going through _resolve()'s gate
            # -- the gate already ran on the turn that SET
            # pending_confirmation; re-running it here would just re-ask
            # the same question forever instead of ever proceeding.
            conversation.pop("pending_confirmation", None)
            if action_name == "clarify":
                return {"action": action_name, "args": args, "tokens_used": tokens_used, "error": None}
            return {"action": pending["action"], "args": pending["args"], "tokens_used": tokens_used, "error": None}

        return _resolve(action_name, args, conversation, tokens_used)

    except Exception as e:
        error = f"Orchestrator call failed: {e}"
        if pending:
            # A failure mid-confirmation must never silently fall through
            # to the destructive default.
            return _ask_reconfirm(
                conversation, 0,
                question="Something went wrong confirming that — did you want me to replace the existing posts?",
                error=error,
            )
        # FIX (bug path #3): previously `return fallback` here too -- the
        # third confirmed bypass, and the one CLAUDE.md's ledger already
        # named as unresolved.
        return _resolve("run_new_request", fallback_args, conversation, 0, error=error)