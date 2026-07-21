"""
conversation/orchestrator.py — Native Tool-Calling Turn Resolver
(patched: see FIX comments for exactly what changed and why)
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
        "description": "Generate fresh content for a new topic/platform request. "
                        "Write ONLY the topic/angle and any standing constraints as "
                        "plain, flowing prose in 1-2 sentences -- e.g. 'AI automation "
                        "project ideas for job-seeking engineers, industry-focused, "
                        "avoid n8n and TensorFlow'. Do NOT specify output format, "
                        "structure, or fields (title/caption/hashtags/tool stack/etc.) "
                        "-- the pipeline already produces that structure for every "
                        "request regardless of what's asked, and restating it here "
                        "has been linked to the downstream topic/category extraction "
                        "misfiring on longer, more complex prompts. Fold in relevant "
                        "context from the conversation (earlier corrections, angle "
                        "changes) -- the pipeline that receives this has NO memory "
                        "of the conversation itself, only what you write here.",
        "parameters": {"type": "object", "properties": {
            "prompt": {"type": "string"},
            "platform": {"type": "string", "enum": ["instagram", "youtube", "tiktok", "linkedin"]},
        }, "required": ["prompt"]},
    }},
    {"type": "function", "function": {
        "name": "edit_existing",
        "description": "Modify wording, tone, or length of already-generated posts.",
        "parameters": {"type": "object", "properties": {
            # FIX: target_posts was previously in "required", forcing the
            # model to always enumerate specific integers -- with no way
            # to express "all of them" and no visibility into how many
            # posts even exist (see the posts-context fix below), this
            # made "edit all posts" requests unreliable. Now optional:
            # omitting it means all posts, matching what main.py's
            # handler already does with args.get("target_posts", "all").
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
    """Sliding window + rolling summary + active constraints + (FIX) the
    posts that actually exist right now, all read from the existing
    conversation dict. Never raises -- degrades to system-prompt-only on
    any failure."""
    try:
        history = conversation.get("message_history", [])
        windowed = history[-SLIDING_WINDOW_TURNS:]

        system_content = SYSTEM_PROMPT
        summary = conversation.get("rolling_summary", "")
        if summary:
            system_content += f"\n\nEARLIER CONVERSATION SUMMARY:\n{summary}"

        # FIX: this was completely missing before. Without it, the model
        # has no reliable way to know how many posts exist, what they're
        # about, or what "post 3" / "the last one" / "the funny one"
        # would even refer to -- edit_existing had no grounding at all.
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
            # FIX: same class of bug as intent_extractor.py and
            # llm_router.py -- openai/gpt-oss-20b is a reasoning model,
            # reasoning_effort defaults to "medium" if unset, and that
            # reasoning competes with the actual summary for the same
            # token budget. Here the failure mode is quiet rather than
            # visible: the except below just swallows it and the summary
            # silently never updates, so long conversations lose memory
            # of whatever aged out of the sliding window without any
            # error appearing anywhere.
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
    except Exception:
        pass


def update_last_tool_result(conversation: dict, summary: str) -> None:
    """FIX: new function. process_turn appends a content-free tool-call
    record ("dispatched:action_name") before main.py's dispatch_action
    has even run, since the real outcome isn't known yet at that point.
    Call this AFTER dispatch_action completes, once conversation state
    (last_output, etc.) reflects what actually happened -- replaces the
    placeholder with the real result so later turns' context (and any
    future summarization) reflects reality instead of a stub string."""
    history = conversation.get("message_history", [])
    for msg in reversed(history):
        if msg.get("role") == "tool":
            msg["content"] = (summary or "")[:500]
            return


def process_turn(conversation: dict, user_message: str) -> dict:
    """
    Resolves ONE turn. Returns {action, args, tokens_used, error}.
    NEVER executes the action -- caller (main.py's dispatch_action) does
    that. Guaranteed to always return a usable dict, never raises.
    """
    conversation.setdefault("message_history", []).append({"role": "user", "content": user_message})

    fallback = {"action": "run_new_request",
                "args": {"prompt": user_message, "platform": conversation.get("last_platform")},
                "tokens_used": 0, "error": None}

    # FIX: Stage-0 shortcut. On the very first message of a session (or
    # any time nothing has been generated yet), there is only one
    # possible correct answer -- there's nothing to edit, exclude-from,
    # or refetch, so it MUST be a fresh request. Every message before
    # this fix paid for a full tool-calling round trip to reach a
    # deterministic conclusion; this mirrors the old gate.py's
    # locked_no_session shortcut, just adapted to this file's contract.
    if not conversation.get("last_generated_posts"):
        return fallback

    try:
        from groq import Groq
        client = Groq(api_key=CONFIG.models.groq_api_key)
        messages = _build_context_messages(conversation)

        response = client.chat.completions.create(
            model=CONFIG.models.groq_model_large,
            temperature=0.0,
            # FIX: same reasoning-model class as the other three fixes
            # (openai/gpt-oss-120b here). No explicit max_tokens cap on
            # this call, so outright truncation is less likely -- but
            # unset reasoning_effort still means "medium" by default,
            # spending real tokens/latency deliberating over what's
            # fundamentally a tool-selection task, not one needing deep
            # reasoning. Consistency + cost, not a fix for an observed
            # failure the way the other three were.
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