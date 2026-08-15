"""
conversation/actions.py — Phase 2 Split B: action implementations

FIX (this session, two separate items):

1. GATEWAY COMPLIANCE: _edit_via_gemini/_edit_via_groq used to import
   `groq`/`google.genai` directly -- a second rule #3 violation besides
   content_generator.py's (now fixed separately). Routed through
   llm/client.py using llm/schemas.py's EditSchema, which that module's
   own docstring confirms was built specifically for this call site.
   generation.content_generator._parse_json is no longer imported here
   -- the gateway's model_validate_json() replaces it entirely.

2. CONFIRMED BUG FIX (flagged in CLAUDE.md/ARCHITECTURE.md/FLOW.md
   across multiple sessions): targeted_refetch() hardcoded
   content_intent="showcase" in both the gate-check state and the real
   fetch input state, silently discarding whatever content_intent the
   conversation was actually using. Now takes content_intent as a
   parameter (default "showcase" preserved for any other caller/test
   that doesn't pass one) -- orchestration/dispatch.py threads the
   conversation's real value through.
"""

import re
from typing import List, Dict, Any

from Config.config import CONFIG
from llm.client import call_gemini, call_groq
from llm.errors import LLMCallFailed, LLMSchemaViolation
from llm.schemas import EditSchema


def _sanitize_constraint_for_query(value: str) -> str:
    return re.sub(r'[:"]', ' ', value).strip()


def _build_edit_prompt(instruction: str, targeted: List[Dict]) -> str:
    import json
    posts_json = json.dumps(targeted, indent=2)
    return f"""You are editing existing social media posts based on a user instruction.

USER INSTRUCTION: "{instruction}"

POSTS TO EDIT (JSON array, {len(targeted)} post(s)):
{posts_json}

Apply the instruction to every post above. Keep the exact same JSON field
structure for each post (number, title, hook, summary, link, caption,
hashtags) — only change what the instruction actually asks for. Keep each
post's original "number" value unchanged. Do not add or remove posts.
Return ONLY this JSON object, nothing else:
{{"posts": [<same {len(targeted)} posts, edited, same field structure>]}}"""
    # FIX: "number" added to the enumerated field list above. EditSchema's
    # PostItem requires "number" (int, no default) -- the old prompt only
    # named title/hook/summary/link/caption/hashtags, which risked the
    # model dropping "number" and failing schema validation on every
    # edit call now that this goes through the gateway's hard-error path.


def _edit_via_gemini(prompt: str) -> "tuple[list, int]":
    result = call_gemini(
        system="You are a senior social media copywriter editing existing posts. "
               "Output your final result in strict, clean JSON matching the requested schema.",
        user=prompt,
        model=CONFIG.models.gemini_model,
        schema=EditSchema,
        temperature=CONFIG.models.generation_temperature,
    )
    return result.content.get("posts", []), result.tokens_used


def _edit_via_groq(prompt: str) -> "tuple[list, int]":
    result = call_groq(
        system="You are a senior social media copywriter editing existing posts. "
               "Output your final result in strict, clean JSON matching the requested schema.",
        user=prompt,
        model=CONFIG.models.groq_model_large,
        schema=EditSchema,
        temperature=CONFIG.models.generation_temperature,
        reasoning_effort="low",
    )
    return result.content.get("posts", []), result.tokens_used


def edit_existing(target_posts, instruction: str, last_generated_posts: List[Dict]) -> dict:
    """
    On total failure (both providers): returns the posts UNCHANGED, and
    ALSO returns "error" with a human-readable reason so the caller can
    distinguish this from success.
    """
    if not last_generated_posts:
        return {"edited_posts": last_generated_posts, "tokens_used": 0, "error": "no_posts_to_edit"}

    if target_posts == "all":
        indices = list(range(len(last_generated_posts)))
    elif isinstance(target_posts, list):
        indices = [i - 1 for i in target_posts if isinstance(i, int) and 1 <= i <= len(last_generated_posts)]
    else:
        indices = []

    if not indices:
        return {"edited_posts": last_generated_posts, "tokens_used": 0, "error": "no_valid_target_posts"}

    targeted = [last_generated_posts[i] for i in indices]
    prompt = _build_edit_prompt(instruction, targeted)

    errors = []
    edited, tokens_used = None, 0

    try:
        edited, tokens_used = _edit_via_gemini(prompt)
    except (LLMCallFailed, LLMSchemaViolation) as e:
        errors.append(f"gemini: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
        try:
            edited, tokens_used = _edit_via_groq(prompt)
        except (LLMCallFailed, LLMSchemaViolation) as e:
            errors.append(f"groq: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
        # Both providers failed, or a schema-valid response still had
        # the wrong post count -- degrade to unedited posts, say so.
        return {
            "edited_posts": last_generated_posts,
            "tokens_used": tokens_used or 0,
            "error": "; ".join(errors) if errors else "malformed_response",
        }

    result_posts = list(last_generated_posts)
    for idx, new_post in zip(indices, edited):
        if isinstance(new_post, dict):
            result_posts[idx] = new_post

    return {"edited_posts": result_posts, "tokens_used": tokens_used, "error": None}


def add_constraint(constraint_type: str, constraint_value: str, active_constraints: List[Dict]) -> dict:
    if constraint_type not in ("exclude", "prefer"):
        constraint_type = "exclude"
    value_clean = (constraint_value or "").strip()
    if not value_clean:
        return {"active_constraints": active_constraints}
    value_lower = value_clean.lower()
    for c in active_constraints:
        if c.get("type") == constraint_type and c.get("value", "").strip().lower() == value_lower:
            return {"active_constraints": active_constraints}
    updated = active_constraints + [{"type": constraint_type, "value": value_clean}]
    return {"active_constraints": updated}


def remove_constraint(constraint_value: str, active_constraints: List[Dict]) -> dict:
    value_lower = (constraint_value or "").strip().lower()
    updated = [c for c in active_constraints if c.get("value", "").strip().lower() != value_lower]
    return {"active_constraints": updated}


def targeted_refetch(topic_delta: str, current_topic: str,
                      leftover_fetch_pool: List[Dict],
                      active_constraints: List[Dict],
                      content_intent: str = "showcase") -> dict:
    exclude_values = [c["value"].lower() for c in active_constraints if c.get("type") == "exclude"]

    def _matches_exclusion(item: Dict) -> bool:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        return any(ev in text for ev in exclude_values)

    filtered_pool = [item for item in leftover_fetch_pool if not _matches_exclusion(item)]
    sources_present = sorted({item.get("_source", item.get("source", "unknown")) for item in filtered_pool})
    fake_state_for_gate = {
        "total_items_fetched": len(filtered_pool),
        "sources_used": sources_present,
        "fetch_retry_count": 0,
        # FIX: was hardcoded "showcase" -- now the conversation's real intent.
        "content_intent": content_intent,
        "fetched_data": {"leftover": filtered_pool},
    }

    from workflow.gates import evaluate_fetch_quality
    result = evaluate_fetch_quality(fake_state_for_gate)

    if result["sufficient"]:
        return {"fetched_data": {"leftover": filtered_pool}, "used_leftover_pool": True}

    combined_topic = f"{current_topic} {topic_delta}".strip()
    exclude_text = " ".join(_sanitize_constraint_for_query(v) for v in exclude_values)
    scoped_query = f"{combined_topic} {exclude_text}".strip() if exclude_text else combined_topic

    from research.fetchers.fetcher_orchestrator import FetcherOrchestrator
    fetch_input_state = {
        "core_topic": combined_topic,
        "fetch_summary": scoped_query,
        "search_queries": [scoped_query],
        # FIX: was hardcoded "showcase" here too.
        "content_intent": content_intent,
        "selected_sources": ["github", "tavily", "google_trends", "youtube", "hackernews"],
        "errors": [],
    }
    fetch_result_state = FetcherOrchestrator().fetch(fetch_input_state)
    return {"fetched_data": fetch_result_state.get("fetched_data", {}), "used_leftover_pool": False}


ACTION_MAP = {
    "edit_existing": edit_existing,
    "add_constraint": add_constraint,
    "remove_constraint": remove_constraint,
    "targeted_refetch": targeted_refetch,
}