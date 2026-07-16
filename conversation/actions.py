"""
conversation/actions.py — Phase 2 Split B: action implementations

Four actions Stage 2 (conversation/gate.py) can dispatch to, plus the
ACTION_MAP registry that IS the single source of truth for valid action
names — gate.py imports and derives VALID_ACTIONS from this, it never
declares its own separate list (this exact duplication caused the
valid_intents bug in Phase 1; not repeating it here).

Security: every function here treats its arguments as untrusted input
from an LLM's classification, not as pre-validated data. Type/shape
validation of args happens at the dispatch boundary in gate.py before
these functions are ever called — these functions still guard against
obviously-empty/malformed input defensively, but the primary validation
point is dispatch-time, not here (single point of truth, not duplicated
defensive code in every action).
"""

import json
import re
from typing import List, Dict, Any

from config import CONFIG

# Reusing the existing proven multi-strategy JSON parser rather than
# writing a third one (per Phase 2 spec's explicit instruction). This
# relies on an underscore-prefixed "private" function being importable —
# Python permits it, but flagging as minor tech debt: a future cleanup
# should promote this into a proper shared utility module instead of
# reaching into another module's private function.
from generation.content_generator import _parse_json as _parse_llm_response


def _sanitize_constraint_for_query(value: str) -> str:
    """
    Strips characters that have special meaning in search query syntax
    (colons, quotes) so a constraint value is always treated as a literal
    keyword, never as accidental query syntax (e.g. a constraint value
    that happens to contain "stars:" shouldn't be read as a GitHub search
    qualifier).
    """
    return re.sub(r'[:"]', ' ', value).strip()


def edit_existing(target_posts, instruction: str, last_generated_posts: List[Dict]) -> dict:
    """
    target_posts: list of 1-based post numbers, or the string "all"
    instruction: natural language edit request, e.g. "make it shorter"
    last_generated_posts: full post dicts (title, hook, caption, summary,
                           link, hashtags) — not the minimal shape used
                           for Stage 2's classification context.

    ONE batched LLM call rewriting all targeted posts together — cost
    discipline, not one call per post. Uses Gemini since this is genuine
    creative rewriting, unlike the gate's classification calls.

    On any failure: returns the posts UNCHANGED, never malformed or
    partially-edited — same degrade-to-simplest-working-behavior
    philosophy used throughout this project.
    """
    if not last_generated_posts:
        return {"edited_posts": last_generated_posts, "tokens_used": 0}

    if target_posts == "all":
        indices = list(range(len(last_generated_posts)))
    elif isinstance(target_posts, list):
        indices = [i - 1 for i in target_posts if isinstance(i, int) and 1 <= i <= len(last_generated_posts)]
    else:
        indices = []

    if not indices:
        return {"edited_posts": last_generated_posts, "tokens_used": 0}

    targeted = [last_generated_posts[i] for i in indices]

    try:
        from google import genai

        client = genai.Client(api_key=CONFIG.models.gemini_api_key)
        posts_json = json.dumps(targeted, indent=2)

        prompt = f"""You are editing existing social media posts based on a user instruction.

USER INSTRUCTION: "{instruction}"

POSTS TO EDIT (JSON array, {len(targeted)} post(s)):
{posts_json}

Apply the instruction to every post above. Keep the exact same JSON field
structure for each post (title, hook, summary, link, caption, hashtags) —
only change what the instruction actually asks for. Do not add or remove
posts. Return ONLY this JSON object, nothing else:
{{"posts": [<same {len(targeted)} posts, edited, same field structure>]}}"""

        response = client.models.generate_content(
            model=CONFIG.models.gemini_model,
            contents=prompt,
        )
        raw = response.text
        parsed = _parse_llm_response(raw)
        edited = parsed.get("posts", [])

        if not isinstance(edited, list) or len(edited) != len(targeted):
            return {"edited_posts": last_generated_posts, "tokens_used": 0}

        result_posts = list(last_generated_posts)
        for idx, new_post in zip(indices, edited):
            if isinstance(new_post, dict):
                result_posts[idx] = new_post

        try:
            tokens_used = response.usage_metadata.total_token_count
        except Exception:
            tokens_used = len(prompt.split()) + len(raw.split())

        return {"edited_posts": result_posts, "tokens_used": tokens_used}

    except Exception:
        return {"edited_posts": last_generated_posts, "tokens_used": 0}


def add_constraint(constraint_type: str, constraint_value: str, active_constraints: List[Dict]) -> dict:
    """
    Pure state mutation, no LLM call. constraint_type must be "exclude"
    or "prefer" — anything else (including malformed/missing) defaults
    to "exclude", since a constraint whose type is unclear is safer
    treated as a thing to avoid than a thing to prioritize.

    Deduplicates: adding the same value+type twice is a no-op, not an
    accumulating list of identical entries over a long session.
    """
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
    """
    Removes any constraint matching constraint_value (case-insensitive),
    regardless of type. If not found, returns the list unchanged — "remove
    something that wasn't there" is a no-op, not an error.
    """
    value_lower = (constraint_value or "").strip().lower()
    updated = [c for c in active_constraints if c.get("value", "").strip().lower() != value_lower]
    return {"active_constraints": updated}


def targeted_refetch(topic_delta: str, current_topic: str,
                      leftover_fetch_pool: List[Dict],
                      active_constraints: List[Dict]) -> dict:
    """
    Step 1: filter leftover_fetch_pool by "exclude" constraints, then
    check sufficiency via workflow/gates.py's evaluate_fetch_quality
    (Phase 1, already tested — not reimplemented here).
    Step 2: if insufficient, trigger a real fetch via
    fetchers/fetcher_orchestrator.py (not a second fetch mechanism),
    scoped to topic_delta + current_topic, with constraint values
    sanitized before being folded into the query.

    KNOWN LIMITATION, flagged rather than silently worked around: this
    function's signature (per the Phase 2 spec) doesn't receive `platform`
    or `content_intent`. Both matter for a fully correct re-fetch — platform
    affects category-based source routing (routing/router_orchestrator.py),
    and content_intent affects the fetch-quality gate's link-requirement
    check. This implementation uses reasonable neutral defaults (a broad
    source list, content_intent="showcase" for the sufficiency check) —
    the integration step should revisit whether this signature needs
    expanding once wired into main.py, rather than this silently guessing
    at values it was never given.
    """
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
        "content_intent": "showcase",  # neutral default — see docstring limitation above
        "fetched_data": {"leftover": filtered_pool},
    }

    from workflow.gates import evaluate_fetch_quality
    result = evaluate_fetch_quality(fake_state_for_gate)

    if result["sufficient"]:
        return {
            "fetched_data": {"leftover": filtered_pool},
            "used_leftover_pool": True,
        }

    # Insufficient — trigger a real fetch scoped to the requested delta.
    combined_topic = f"{current_topic} {topic_delta}".strip()
    exclude_text = " ".join(_sanitize_constraint_for_query(v) for v in exclude_values)
    scoped_query = f"{combined_topic} {exclude_text}".strip() if exclude_text else combined_topic

    from fetchers.fetcher_orchestrator import FetcherOrchestrator

    fetch_input_state = {
        "core_topic": combined_topic,
        "fetch_summary": scoped_query,
        "search_queries": [scoped_query],
        "content_intent": "showcase",  # same neutral-default limitation as above
        "selected_sources": ["github", "tavily", "google_trends", "youtube", "hackernews"],
        "errors": [],
    }

    orchestrator = FetcherOrchestrator()
    fetch_result_state = orchestrator.fetch(fetch_input_state)

    return {
        "fetched_data": fetch_result_state.get("fetched_data", {}),
        "used_leftover_pool": False,
    }


# ── Single source of truth for valid action names ──────────────────
# gate.py imports and derives VALID_ACTIONS from THIS dict — it never
# declares its own separate list (mirrors fetchers/fetcher_orchestrator.py's
# FETCHER_MAP pattern exactly).
ACTION_MAP = {
    "edit_existing": edit_existing,
    "add_constraint": add_constraint,
    "remove_constraint": remove_constraint,
    "targeted_refetch": targeted_refetch,
}