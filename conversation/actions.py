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


def _edit_via_gemini(prompt: str):
    result = call_gemini(
        system="You are a senior social media copywriter editing existing posts. "
               "Output your final result in strict, clean JSON matching the requested schema.",
        user=prompt,
        model=CONFIG.models.gemini_model,
        schema=EditSchema,
        temperature=CONFIG.models.generation_temperature,
    )
    return result.content.get("posts", []), result.tokens_used


def _edit_via_groq(prompt: str):
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
        tokens_used += getattr(e, "tokens_used", 0)
        errors.append(f"gemini: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
        try:
            edited, tokens_used = _edit_via_groq(prompt)
        except (LLMCallFailed, LLMSchemaViolation) as e:
            tokens_used += getattr(e, "tokens_used", 0)
            errors.append(f"groq: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
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

    # FIX (Bug 5): Compute combined_topic early so fake_state_for_gate can
    # include search_queries. evaluate_fetch_quality reads
    # state.get("search_queries", []) when building a next_query for retries;
    # without this key the gate always returned next_query=None from this path.
    combined_topic = f"{current_topic} {topic_delta}".strip()

    fake_state_for_gate = {
        "total_items_fetched": len(filtered_pool),
        "sources_used": sources_present,
        "fetch_retry_count": 0,
        "content_intent": content_intent,
        "fetched_data": {"leftover": filtered_pool},
        "search_queries": [combined_topic],
    }

    from workflow.gates import evaluate_fetch_quality
    result = evaluate_fetch_quality(fake_state_for_gate)

    if result["sufficient"]:
        return {"fetched_data": {"leftover": filtered_pool}, "used_leftover_pool": True}

    exclude_text = " ".join(_sanitize_constraint_for_query(v) for v in exclude_values)
    scoped_query = f"{combined_topic} {exclude_text}".strip() if exclude_text else combined_topic

    from research.fetchers.fetcher_orchestrator import FetcherOrchestrator
    from core.state import create_initial_state
    import uuid as _uuid
    # FIX (found by actually running this path -- see orchestration/
    # dispatch.py's matching fix for the full explanation): was a bare
    # dict missing "logs", which crashed with KeyError the moment
    # FetcherOrchestrator.fetch() called add_log() on it.
    fetch_input_state = create_initial_state(raw_prompt=combined_topic, session_id=str(_uuid.uuid4())[:8])
    fetch_input_state["core_topic"] = combined_topic
    fetch_input_state["fetch_summary"] = scoped_query
    fetch_input_state["search_queries"] = [scoped_query]
    fetch_input_state["content_intent"] = content_intent
    fetch_input_state["selected_sources"] = ["github", "tavily", "google_trends", "youtube", "hackernews"]
    fetch_result_state = FetcherOrchestrator().fetch(fetch_input_state)
    return {"fetched_data": fetch_result_state.get("fetched_data", {}), "used_leftover_pool": False}


ACTION_MAP = {
    "edit_existing": edit_existing,
    "add_constraint": add_constraint,
    "remove_constraint": remove_constraint,
    "targeted_refetch": targeted_refetch,
}