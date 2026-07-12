"""
workflow/gates.py — Phase 1 evaluation gates

Pure, deterministic functions. Neither function mutates state or calls
any fetcher/LLM. Both are cheap pre-filters (per the project's standing
rule against hardcoded judgment logic replacing real judgment) — these
gates only check structural sufficiency, not content quality. Tier 2
(LLM-based qualitative critique) is explicitly out of scope this phase.

Not wired into any graph yet — workflow/graph.py imports and attaches
these in the integration step.
"""

from typing import Dict, Any
from core.state import TrendForgeState
from config import PLATFORM_SETTINGS

MIN_ITEMS_FLOOR = 3          # total_items_fetched below this = insufficient
MAX_FETCH_RETRIES = 2
MAX_GENERATION_RETRIES = 2

# Structural pattern check, not a content-quality judgment call — a link
# pointing at a search engine's results page is never "a specific source,"
# regardless of what content_intent or topic is involved. Found via a real
# run: when fallback sources (google_trends/hackernews) return a
# constructed search-query URL as their "link" field, the non-empty check
# alone waves it through as if it were a genuine source.
GENERIC_SEARCH_URL_PATTERNS = ("google.com/search", "bing.com/search", "duckduckgo.com/?q=")


def _is_generic_search_url(link: str) -> bool:
    link_l = link.lower()
    return any(p in link_l for p in GENERIC_SEARCH_URL_PATTERNS)


def evaluate_fetch_quality(state: TrendForgeState) -> Dict[str, Any]:
    """
    Checks whether fetched data is sufficient to proceed to generation.

    Returns:
        {
            "sufficient": bool,
            "reason": str,
            "should_retry": bool,             # False once retry cap is hit
            "next_query": str | None,         # next unused search_queries variant
        }
    """
    total_items = state.get("total_items_fetched", 0)
    sources_used = state.get("sources_used", [])
    retry_count = state.get("fetch_retry_count", 0)

    has_returning_source = len(sources_used) > 0
    sufficient = total_items >= MIN_ITEMS_FLOOR and has_returning_source

    if sufficient:
        return {
            "sufficient": True,
            "reason": f"{total_items} items from {len(sources_used)} source(s) — meets floor of {MIN_ITEMS_FLOOR}",
            "should_retry": False,
            "next_query": None,
        }

    if not has_returning_source:
        reason = "no source in sources_used returned any items"
    else:
        reason = f"only {total_items} items fetched, below floor of {MIN_ITEMS_FLOOR}"

    retry_available = retry_count < MAX_FETCH_RETRIES
    next_query = None
    if retry_available:
        queries = state.get("search_queries", [])
        # Cycle to the next unused variant rather than repeating the same
        # query — intent_extractor.py already generates up to 3 angles,
        # reuse that instead of a new LLM call for retry-query generation.
        if queries:
            next_index = retry_count + 1
            if next_index < len(queries):
                next_query = queries[next_index]
            else:
                next_query = queries[-1]  # exhausted variants, reuse last rather than error

    return {
        "sufficient": False,
        "reason": reason,
        "should_retry": retry_available,
        "next_query": next_query,
    }


def evaluate_post_validation(state: TrendForgeState) -> Dict[str, Any]:
    """
    Tier 1 (deterministic) validation only. Tier 2 (LLM qualitative
    critique) is explicitly out of scope for this phase — no trigger
    condition has been defined for it yet.

    Returns:
        {
            "valid": bool,
            "errors": List[str],   # one entry per failed check, human-readable
            "should_retry": bool,
        }
    """
    posts = state.get("generated_posts", [])
    platform = state.get("platform", "instagram")
    content_intent = state.get("content_intent", "showcase")
    data_starved = state.get("data_starved", False)
    retry_count = state.get("generation_retry_count", 0)

    errors = []

    if not posts:
        errors.append("generated_posts is empty")
    else:
        max_caption_chars = PLATFORM_SETTINGS.get(platform, {}).get("max_caption_chars", 2200)

        # Per generation/prompts.py's link_guide per intent — read from
        # there, not redefined independently here.
        link_required_intents = {"showcase", "news", "review"}
        link_optional_intents = {"educate", "inspire"}

        seen_titles = set()

        for i, post in enumerate(posts):
            label = f"post {i + 1}"

            for field in ("title", "hook", "caption"):
                if not post.get(field):
                    errors.append(f"{label}: missing or empty '{field}'")

            summary = post.get("summary")
            if not isinstance(summary, list) or not summary:
                errors.append(f"{label}: 'summary' must be a non-empty list")

            hashtags = post.get("hashtags")
            if not isinstance(hashtags, list) or not hashtags:
                errors.append(f"{label}: 'hashtags' must be a non-empty list")

            # Link rule — data_starved overrides the normal per-intent
            # requirement regardless of what content_intent says.
            link = post.get("link", "")
            if not data_starved and content_intent in link_required_intents and not link:
                errors.append(f"{label}: link is required for content_intent='{content_intent}' but is empty")
            # link_optional_intents and data_starved=True: no check needed, empty is fine.

            caption = post.get("caption", "")
            if isinstance(caption, str) and len(caption) > max_caption_chars:
                errors.append(f"{label}: caption is {len(caption)} chars, exceeds {platform}'s {max_caption_chars} limit")

            title = post.get("title", "")
            title_key = title.strip().lower()
            if title_key and title_key in seen_titles:
                errors.append(f"{label}: title is a near-duplicate of an earlier post in this batch ('{title}')")
            seen_titles.add(title_key)

    valid = len(errors) == 0
    retry_available = retry_count < MAX_GENERATION_RETRIES

    return {
        "valid": valid,
        "errors": errors,
        "should_retry": (not valid) and retry_available,
    }