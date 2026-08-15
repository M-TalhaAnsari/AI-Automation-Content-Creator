"""
orchestration/conversation_agent.py — Native Tool-Calling Turn Resolver

FIX (this session): confirmed bug in the pending-confirmation branch.
While a confirmation is pending, ALL 8 tools remain available to the
model -- the instruction to only call run_new_request or clarify is
prose in the system prompt, not an enforced tool_choice restriction.
The old code discarded ANY tool call other than "clarify" and force-ran
the pending action regardless -- so if the user's reply actually meant
"no, undo that instead" and the model correctly called `undo`, that
call was silently thrown away and the original destructive action ran
anyway. Now: only an exact repeat of the pending action counts as
confirmation; anything else (clarify, or a genuinely different action)
is dispatched as what the user actually asked for, going back through
_resolve() so a different destructive action gets its own fresh
confirmation gate.

KNOWN RESIDUAL LIMITATION, not solved here: if the model calls the SAME
action name as the pending one but with DIFFERENT args (e.g. pending was
run_new_request for topic A, and the new turn's reply -- ambiguously --
resolves to run_new_request for topic B), this still treats it as
confirming the ORIGINAL pending args, same as before this fix. That's a
preexisting behavior, not something this fix changes for the worse;
flagging it rather than silently expanding this fix's scope further.
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
    conversation.pop("pending_confirmation", None)
    question = question or "Just to confirm — did you want me to go ahead and replace the existing posts?"
    conversation.setdefault("message_history", []).append({"role": "assistant", "content": question})
    return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": tokens_used, "error": error}


def process_turn(conversation: dict, user_message: str) -> dict:
    conversation.setdefault("message_history", []).append({"role": "user", "content": user_message})

    fallback_args = {"prompt": user_message, "platform": conversation.get("last_platform")}

    if not conversation.get("last_generated_posts"):
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
                return _ask_reconfirm(conversation, tokens_used)
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
                return _ask_reconfirm(conversation, tokens_used, error=error)
            return _resolve("run_new_request", fallback_args, conversation, tokens_used, error=error)

        conversation["message_history"].append({
            "role": "tool", "tool_call_id": call.id, "content": f"dispatched:{action_name}",
        })

        if pending:
            conversation.pop("pending_confirmation", None)
            # FIX: previously, only "clarify" was special-cased here --
            # ANY OTHER tool call (e.g. a correctly-resolved `undo` in
            # response to the user changing their mind) was discarded
            # and pending["action"] was force-run regardless. Now: only
            # an exact repeat of the pending action counts as
            # confirmation. Everything else is dispatched as what the
            # user actually asked for, via _resolve() -- so a different
            # destructive action still gets its own confirmation gate.
            if action_name == pending["action"]:
                return {"action": pending["action"], "args": pending["args"], "tokens_used": tokens_used, "error": None}
            return _resolve(action_name, args, conversation, tokens_used)

        return _resolve(action_name, args, conversation, tokens_used)

    except Exception as e:
        error = f"Orchestrator call failed: {e}"
        if pending:
            return _ask_reconfirm(
                conversation, 0,
                question="Something went wrong confirming that — did you want me to replace the existing posts?",
                error=error,
            )
        return _resolve("run_new_request", fallback_args, conversation, 0, error=error)