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
import logging
import re
from Config.config import CONFIG
from llm.client import call_gemini, call_groq
from llm.schemas import ConversationTurnSchema
from llm.errors import LLMCallFailed, LLMSchemaViolation

logger = logging.getLogger("trendforge.orchestration.conversation_agent")

SYSTEM_PROMPT = (
    "You are TrendForge's conversation assistant. The user is managing social media content.\n\n"
    "CRITICAL ACTION ROUTING RULES:\n"
    "1. `edit_existing`: Call this whenever the user wants to edit, update, refine, or ADD sections "
    "(such as 'add pros and cons', 'add bullet points', 'include takeaways', 'make longer/shorter') "
    "to the currently generated posts. If the user mentions 'above posts', 'each post', 'all posts', "
    "or refers to specific post numbers, this is ALWAYS `edit_existing`. NEVER use `run_new_request` for modifications!\n"
    "2. `generate_more`: Call this when the user wants ADDITIONAL posts on the same general topic "
    "('one more', 'give me 2 more', 'another post on this').\n"
    "3. `run_new_request`: ONLY call this when the user introduces a completely NEW, unrelated topic "
    "(e.g., 'now make posts about fitness', 'let's switch to crypto').\n"
    "4. If genuinely ambiguous, call `clarify`."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "run_new_request",
        "description": "Generate fresh content for a completely NEW, unrelated topic. NEVER call this when the user refers to existing/above posts.",
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
                        "or specific type of content for these NEW posts, "
                        "capture that in topic_delta. DO NOT use this if the user wants to "
                        "CHANGE or EDIT an already generated post (e.g., 'change post 2', "
                        "'make them shorter'). Use edit_existing for modifications. Do NOT "
                        "use run_new_request for this.",
        "parameters": {"type": "object", "properties": {
            "count": {"type": "integer", "description": "How many additional posts. Default 1 if not specified."},
            "topic_delta": {"type": "string", "description": "Any refinement, new angle, "
                            "or specific instruction for these additional posts, beyond "
                            "just 'more of the same' -- e.g. 'project ideas that "
                            "implement these strategies'. Empty "
                            "string if truly just more of the exact same thing."},
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "edit_existing",
        "description": "Modify, expand, refine, or add sections (e.g. 'add pros and cons', 'more bullet points', 'make shorter') to already-generated posts.",
        "parameters": {"type": "object", "properties": {
            "target_posts": {
                "type": "array", "items": {"type": "integer"},
                "description": "1-based post numbers to target (e.g. [1] or [1, 2]). Omit this field entirely if the user means ALL current posts.",
            },
            "instruction": {
                "type": "string",
                "description": "The exact modification instruction to apply to the post(s).",
            },
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
    posts = conversation.get("last_generated_posts") or []

    if not posts:
        EDIT_INTENT_PATTERN = re.compile(
            r"\b(above posts?|previous posts?|edit post|change post|update post|for all the above|in all posts?|make them|add .* to (the|all|each) post)\b",
            re.IGNORECASE,
        )
        if EDIT_INTENT_PATTERN.search(user_message):
            question = "There are no previous posts loaded in this session to edit. Please create a set of posts first, or tell me what topic you'd like to post about!"
            conversation.setdefault("message_history", []).append({"role": "assistant", "content": question})
            return {"action": "clarify", "args": {"clarify_question": question}, "tokens_used": 0, "error": None}

        return _resolve("run_new_request", fallback_args, conversation, 0)

    pending = conversation.get("pending_confirmation")

    # Fast deterministic resolution for pending confirmations (avoids LLM loop on "OK", "YES", etc.)
    if pending:
        clean_msg = user_message.strip().lower()
        AFFIRMATIVE_PATTERN = re.compile(
            r"^(yes|y|ok|okay|yeah|yep|sure|proceed|confirm|go ahead|do it|apply|change it|update it|replace it|do that)\b",
            re.IGNORECASE,
        )
        NEGATIVE_PATTERN = re.compile(r"^(no|nope|cancel|stop|nevermind|abort|don't|dont)\b", re.IGNORECASE)

        if AFFIRMATIVE_PATTERN.search(clean_msg):
            conversation.pop("pending_confirmation", None)
            return {
                "action": pending["action"],
                "args": pending["args"],
                "tokens_used": 0,
                "error": None,
            }
        elif NEGATIVE_PATTERN.search(clean_msg):
            conversation.pop("pending_confirmation", None)
            cancellation = "Understood — I've kept your existing posts as they are."
            conversation.setdefault("message_history", []).append({"role": "assistant", "content": cancellation})
            return {"action": "clarify", "args": {"clarify_question": cancellation}, "tokens_used": 0, "error": None}

    # -------------------------------------------------------------
    # Fast Deterministic Shortcuts (0ms, 0 tokens, no LLM failure)
    # -------------------------------------------------------------
    clean_msg = user_message.strip()

    # 1. Edit all posts: "For all the above post add pros and cons...", "All posts: add ...", "In all posts ..."
    m_all = re.search(
        r"^(?:for\s+)?(?:all\s+(?:the\s+)?(?:above\s+)?posts?|every\s+post|in\s+all\s+posts?)\s*[,:]?\s*(.+)$",
        clean_msg,
        re.IGNORECASE,
    )
    if m_all:
        instruction = m_all.group(1).strip()
        args = {"target_posts": "all", "instruction": instruction}
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": "dispatched:edit_existing"})
        return _resolve("edit_existing", args, conversation, tokens_used=0)

    # 2. Edit single/specific post: "For post 1: ...", "In post 2, ...", "Post 3: ...", "Edit post 1: ..."
    m_single = re.search(
        r"^(?:(?:for|in|on|edit|update)\s+)?post\s+(\d+)\s*[,:]?\s*(.+)$",
        clean_msg,
        re.IGNORECASE,
    )
    if m_single:
        post_num = int(m_single.group(1))
        instruction = m_single.group(2).strip()
        args = {"target_posts": [post_num], "instruction": instruction}
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": "dispatched:edit_existing"})
        return _resolve("edit_existing", args, conversation, tokens_used=0)

    # 3. Add section / pros and cons across existing posts: "Add pros and cons to each post", "Add bullet points"
    m_section = re.search(
        r"\b(add|include|put)\s+(?:the\s+)?(?:pros\s+and\s+cons|advantages\s+and\s+disadvantages|bullet\s+points?|takeaways?|summary)\b",
        clean_msg,
        re.IGNORECASE,
    )
    if m_section:
        args = {"target_posts": "all", "instruction": clean_msg}
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": "dispatched:edit_existing"})
        return _resolve("edit_existing", args, conversation, tokens_used=0)

    # 4. Modify style / length across existing posts: "Make them shorter", "Make all posts punchier"
    m_make = re.search(
        r"^(?:make\s+(?:them|all\s+posts|the\s+posts|everything)|shorten\s+(?:them|all\s+posts))\s*(.*)$",
        clean_msg,
        re.IGNORECASE,
    )
    if m_make:
        args = {"target_posts": "all", "instruction": clean_msg}
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": "dispatched:edit_existing"})
        return _resolve("edit_existing", args, conversation, tokens_used=0)

    # 5. Undo
    if re.match(r"^(?:undo|revert|put it back|go back)\b", clean_msg, re.IGNORECASE):
        conversation.setdefault("message_history", []).append({"role": "assistant", "content": "dispatched:undo"})
        return _resolve("undo", {}, conversation, tokens_used=0)

    # -------------------------------------------------------------
    # LLM Resolution (Gemini with Groq fallback)
    # -------------------------------------------------------------
    try:
        messages = _build_context_messages(conversation, pending_confirmation=pending)
        system_str = messages[0]["content"] if messages and messages[0].get("role") == "system" else SYSTEM_PROMPT

        history_parts = []
        for m in messages[1:]:
            r = m.get("role", "user").upper()
            c = m.get("content", "")
            if c:
                history_parts.append(f"{r}: {c}")

        user_prompt = ""
        if history_parts:
            user_prompt += "RECENT CONVERSATION HISTORY:\n" + "\n".join(history_parts[-8:]) + "\n\n"
        user_prompt += f"CURRENT USER MESSAGE:\n{user_message}"

        llm_res = None
        try:
            llm_res = call_gemini(
                system=system_str,
                user=user_prompt,
                model=CONFIG.models.gemini_model,
                schema=ConversationTurnSchema,
                temperature=0.0,
            )
        except Exception as gemini_err:
            logger.warning(f"call_gemini turn resolution failed: {gemini_err}. Trying call_groq fallback...")
            try:
                llm_res = call_groq(
                    system=system_str,
                    user=user_prompt,
                    model=CONFIG.models.groq_model_large,
                    schema=ConversationTurnSchema,
                    temperature=0.0,
                )
            except Exception as groq_err:
                logger.error(f"Both Gemini and Groq failed in conversation_agent: {groq_err}")
                raise gemini_err

        tokens_used = llm_res.tokens_used if llm_res else 0
        data = llm_res.content if llm_res and isinstance(llm_res.content, dict) else {}
        action_name = data.get("action", "run_new_request")

        if action_name == "edit_existing":
            tp = data.get("target_posts")
            instr = data.get("instruction") or user_message
            args = {"target_posts": tp if tp else "all", "instruction": instr}
        elif action_name == "run_new_request":
            args = {
                "prompt": data.get("prompt") or user_message,
                "platform": conversation.get("last_platform"),
            }
        elif action_name == "generate_more":
            args = {
                "count": data.get("count", 1),
                "topic_delta": data.get("topic_delta", ""),
            }
        elif action_name == "add_constraint":
            args = {
                "constraint_type": data.get("constraint_type", "exclude"),
                "constraint_value": data.get("constraint_value", ""),
            }
        elif action_name == "remove_constraint":
            args = {
                "constraint_value": data.get("constraint_value", ""),
            }
        elif action_name == "targeted_refetch":
            args = {
                "topic_delta": data.get("topic_delta", ""),
            }
        elif action_name == "undo":
            args = {}
        elif action_name == "clarify":
            args = {
                "clarify_question": data.get("clarify_question") or "Could you clarify what you'd like to do?",
            }
        else:
            args = fallback_args
            action_name = "run_new_request"

        conversation.setdefault("message_history", []).append({
            "role": "assistant",
            "content": f"dispatched:{action_name}",
        })

        if pending:
            conversation.pop("pending_confirmation", None)
            if action_name == pending["action"]:
                return {"action": pending["action"], "args": pending["args"], "tokens_used": tokens_used, "error": None}
            return _resolve(action_name, args, conversation, tokens_used)

        return _resolve(action_name, args, conversation, tokens_used)

    except Exception as e:
        error = f"Orchestrator call failed: {e}"
        logger.error(error)
        if pending:
            return _ask_reconfirm(
                conversation, 0,
                question="Something went wrong confirming that — did you want me to replace the existing posts?",
                error=error,
            )
        return _resolve("run_new_request", fallback_args, conversation, 0, error=error)