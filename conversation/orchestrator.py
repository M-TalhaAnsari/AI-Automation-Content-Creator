"""
conversation/orchestrator.py — Native Tool-Calling Turn Resolver
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
        "description": "User wants ADDITIONAL post(s) on the SAME topic as what's already "
                        "been generated -- adds to the existing set rather than replacing it "
                        "or editing it. Use for 'one more', 'give me another', 'a few more of "
                        "these'. Do NOT use run_new_request for this -- that tool is only for "
                        "a genuinely different, unrelated topic.",
        "parameters": {"type": "object", "properties": {
            "count": {"type": "integer", "description": "How many additional posts. Default 1 if not specified."},
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


def process_turn(conversation: dict, user_message: str) -> dict:
    conversation.setdefault("message_history", []).append({"role": "user", "content": user_message})

    fallback = {"action": "run_new_request",
                "args": {"prompt": user_message, "platform": conversation.get("last_platform")},
                "tokens_used": 0, "error": None}

    if not conversation.get("last_generated_posts"):
        return fallback

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
                # ambiguous -- default to asking again, never to the
                # destructive fallback.
                conversation.pop("pending_confirmation", None)
                question = "Just to confirm — did you want me to go ahead and replace the existing posts?"
                return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": tokens_used, "error": None}
            fallback["tokens_used"] = tokens_used
            return fallback

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
            fallback["tokens_used"] = tokens_used
            fallback["error"] = f"Invalid tool call: {action_name!r} / {args!r}"
            if pending:
                conversation.pop("pending_confirmation", None)
            return fallback

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
            conversation.pop("pending_confirmation", None)
            if action_name == "clarify":
                return {"action": action_name, "args": args, "tokens_used": tokens_used, "error": None}
            return {"action": pending["action"], "args": pending["args"], "tokens_used": tokens_used, "error": None}

        if action_name in DESTRUCTIVE_ACTIONS and conversation.get("last_generated_posts"):
            count = len(conversation["last_generated_posts"])
            conversation["pending_confirmation"] = {"action": action_name, "args": args}
            question = (
                f"This will replace your {count} existing post(s) with new content — "
                f"reply to confirm, or tell me if you meant something else."
            )
            conversation["message_history"].append({"role": "assistant", "content": question})
            return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": tokens_used, "error": None}

        return {"action": action_name, "args": args, "tokens_used": tokens_used, "error": None}

    except Exception as e:
        fallback["error"] = f"Orchestrator call failed: {e}"
        if pending:
            # A failure mid-confirmation must never silently fall through
            # to the destructive default.
            conversation.pop("pending_confirmation", None)
            return {
                "action": "clarify",
                "args": {"clarify_question": "Something went wrong confirming that — did you want me to replace the existing posts?"},
                "tokens_used": 0, "error": fallback["error"],
            }
        return fallback