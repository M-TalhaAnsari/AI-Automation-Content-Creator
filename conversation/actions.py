"""
conversation/actions.py — Phase 2 Split B: action implementations
(edit_existing patched: Groq fallback + honest error signaling. See
inline comments marked FIX for exactly what changed and why.)
"""

import json
import re
from typing import List, Dict, Any

from config import CONFIG
from generation.content_generator import _parse_json as _parse_llm_response


def _sanitize_constraint_for_query(value: str) -> str:
    return re.sub(r'[:"]', ' ', value).strip()


def _build_edit_prompt(instruction: str, targeted: List[Dict]) -> str:
    posts_json = json.dumps(targeted, indent=2)
    return f"""You are editing existing social media posts based on a user instruction.

USER INSTRUCTION: "{instruction}"

POSTS TO EDIT (JSON array, {len(targeted)} post(s)):
{posts_json}

Apply the instruction to every post above. Keep the exact same JSON field
structure for each post (title, hook, summary, link, caption, hashtags) —
only change what the instruction actually asks for. Do not add or remove
posts. Return ONLY this JSON object, nothing else:
{{"posts": [<same {len(targeted)} posts, edited, same field structure>]}}"""


def _edit_via_gemini(prompt: str) -> (list, int):
    from google import genai
    client = genai.Client(api_key=CONFIG.models.gemini_api_key)
    response = client.models.generate_content(model=CONFIG.models.gemini_model, contents=prompt)
    raw = response.text
    parsed = _parse_llm_response(raw)
    edited = parsed.get("posts", [])
    try:
        tokens_used = response.usage_metadata.total_token_count
    except Exception:
        tokens_used = len(prompt.split()) + len(raw.split())
    return edited, tokens_used


def _edit_via_groq(prompt: str) -> (list, int):
    # FIX: this fallback didn't exist before. ContentGenerator already
    # falls back to Groq when Gemini fails (visible in every real log as
    # "Trying Groq Fallback... Generated N posts via Groq-LLaMA3") --
    # edit_existing had no equivalent, so it silently no-op'd instead.
    from groq import Groq
    client = Groq(api_key=CONFIG.models.groq_api_key)
    response = client.chat.completions.create(
        model=CONFIG.models.groq_model_large,
        temperature=0.3,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content
    parsed = _parse_llm_response(raw)
    edited = parsed.get("posts", [])
    tokens_used = getattr(response.usage, "total_tokens", 0) if response.usage else 0
    return edited, tokens_used


def edit_existing(target_posts, instruction: str, last_generated_posts: List[Dict]) -> dict:
    """
    On total failure (both providers): returns the posts UNCHANGED, same
    as before, but now ALSO returns "error" with a human-readable reason
    -- FIX: previously this was indistinguishable from success. main.py's
    _handle_edit_existing (patched separately) now checks this field.
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
    except Exception as e:
        errors.append(f"gemini: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
        try:
            edited, tokens_used = _edit_via_groq(prompt)
        except Exception as e:
            errors.append(f"groq: {e}")

    if not isinstance(edited, list) or len(edited) != len(targeted):
        # Both providers failed or returned a malformed shape -- degrade
        # to unedited posts (unchanged philosophy), but now say so.
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
                      active_constraints: List[Dict]) -> dict:
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
        "content_intent": "showcase",
        "fetched_data": {"leftover": filtered_pool},
    }

    from workflow.gates import evaluate_fetch_quality
    result = evaluate_fetch_quality(fake_state_for_gate)

    if result["sufficient"]:
        return {"fetched_data": {"leftover": filtered_pool}, "used_leftover_pool": True}

    combined_topic = f"{current_topic} {topic_delta}".strip()
    exclude_text = " ".join(_sanitize_constraint_for_query(v) for v in exclude_values)
    scoped_query = f"{combined_topic} {exclude_text}".strip() if exclude_text else combined_topic

    from fetchers.fetcher_orchestrator import FetcherOrchestrator
    fetch_input_state = {
        "core_topic": combined_topic,
        "fetch_summary": scoped_query,
        "search_queries": [scoped_query],
        "content_intent": "showcase",
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