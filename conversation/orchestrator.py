"""
conversation/orchestrator.py — Native Tool-Calling Turn Resolver
"""

import json
from config import CONFIG

SYSTEM_PROMPT = (
    "You are TrendForge's conversation assistant. The user is generating "
    "social media content. Decide, for each message, whether to call a "
    "tool to modify/refine existing content or preferences, or call "
    "run_new_request for a fresh, unrelated content request. If genuinely "
    "uncertain what the user wants, call clarify and ask — do not guess "
    "at destructive or content-altering actions."
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
        "name": "clarify",
        "description": "The request is too ambiguous to act on safely. Ask the user a specific question instead of guessing.",
        "parameters": {"type": "object", "properties": {
            "clarify_question": {"type": "string"},
        }, "required": ["clarify_question"]},
    }},
]

VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

SLIDING_WINDOW_TURNS = 20
MAX_HISTORY_TOKENS = 6000


def _rough_tokens(messages) -> int:
    try:
        return sum(len(str(m.get("content", ""))) for m in messages) // 4
    except Exception:
        return 0


def _build_context_messages(conversation: dict) -> list:
    try:
        history = conversation.get("message_history", [])
        windowed = history[-SLIDING_WINDOW_TURNS:]

        system_content = SYSTEM_PROMPT
        summary = conversation.get("rolling_summary", "")
        if summary:
            system_content += f"\n\nEARLIER CONVERSATION SUMMARY:\n{summary}"

        posts = conversation.get("last_generated_posts") or []
        if posts:
            titles = "\n".join(f"{i}. {p.get('title', '(untitled)')}" for i, p in enumerate(posts, 1))
            system_content += f"\n\nCURRENTLY GENERATED POSTS ({len(posts)} total):\n{titles}"

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

    try:
        from groq import Groq
        client = Groq(api_key=CONFIG.models.groq_api_key)
        messages = _build_context_messages(conversation)

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
            return fallback

        conversation["message_history"].append({
            "role": "tool", "tool_call_id": call.id, "content": f"dispatched:{action_name}",
        })

        return {"action": action_name, "args": args, "tokens_used": tokens_used, "error": None}

    except Exception as e:
        fallback["error"] = f"Orchestrator call failed: {e}"
        return fallback