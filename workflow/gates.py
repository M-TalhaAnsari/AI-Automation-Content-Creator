from typing import Dict, Any
from core.state import TrendForgeState
from Config.config import PLATFORM_SETTINGS
from llm.client import call_groq
from llm.schemas import ItemKindCheckSchema


MIN_ITEMS_FLOOR = 3
MAX_FETCH_RETRIES = 2
MAX_GENERATION_RETRIES = 2

GENERIC_SEARCH_URL_PATTERNS = ("google.com/search", "bing.com/search", "duckduckgo.com/?q=")

_ITEM_KIND_SYSTEM_PROMPT = (
    'You check whether generated titles match a requested category. For each '
    'title, decide whether it genuinely names a specific instance of '
    '"{item_kind}" (not a related practice, technique, or adjacent concept).'
)


def _is_generic_search_url(link: str) -> bool:
    link_l = link.lower()
    return any(p in link_l for p in GENERIC_SEARCH_URL_PATTERNS)


LINK_REQUIRED_INTENTS = {"showcase", "news", "review"}


def evaluate_fetch_quality(state: TrendForgeState) -> Dict[str, Any]:
    fetched_data = state.get("fetched_data", {})
    total_items = sum(len(items) for items in fetched_data.values())
    sources_used = [src for src, items in fetched_data.items() if items]
    retry_count = state.get("fetch_retry_count", 0)
    content_intent = state.get("content_intent", "showcase")

    has_returning_source = len(sources_used) > 0
    count_sufficient = total_items >= MIN_ITEMS_FLOOR and has_returning_source

    link_quality_ok = True
    if content_intent in LINK_REQUIRED_INTENTS:
        all_links = [
            item.get("link", "")
            for items in fetched_data.values()
            for item in items
            if item.get("link")
        ]
        if all_links and all(_is_generic_search_url(l) for l in all_links):
            link_quality_ok = False

    sufficient = count_sufficient and link_quality_ok

    if sufficient:
        return {
            "sufficient": True,
            "reason": f"{total_items} items from {len(sources_used)} source(s) — meets floor of {MIN_ITEMS_FLOOR}",
            "should_retry": False,
            "next_query": None,
        }

    if not has_returning_source:
        reason = "no source in sources_used returned any items"
    elif not count_sufficient:
        reason = f"only {total_items} items fetched, below floor of {MIN_ITEMS_FLOOR}"
    else:
        reason = ("all fetched items have generic search-engine links, not real sources — "
                   "regenerating content won't fix this, need different fetched data")

    retry_available = retry_count < MAX_FETCH_RETRIES
    next_query = None
    if retry_available:
        queries = state.get("search_queries", [])
        if queries:
            next_index = retry_count + 1
            if next_index < len(queries):
                next_query = queries[next_index]
            else:
                next_query = queries[-1]

    return {
        "sufficient": False,
        "reason": reason,
        "should_retry": retry_available,
        "next_query": next_query,
    }


def evaluate_item_kind_match(state: TrendForgeState) -> Dict[str, Any]:
    item_kind = state.get("item_kind", "")
    posts = state.get("generated_posts", [])
    retry_count = state.get("generation_retry_count", 0)

    if not item_kind or not posts:
        return {"valid": True, "errors": [], "should_retry": False}

    titles = [p.get("title", "") for p in posts]
    user_prompt = f"""Titles generated:
{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(titles))}"""

    try:
        from Config.config import CONFIG
        result = call_groq(
            system=_ITEM_KIND_SYSTEM_PROMPT.format(item_kind=item_kind),
            user=user_prompt,
            model=CONFIG.models.groq_model_small,
            schema=ItemKindCheckSchema,
            temperature=0.0,
            reasoning_effort="low",
        )
        mismatched = result.content.get("mismatched_indices", [])
    except Exception:
        return {"valid": True, "errors": [], "should_retry": False}

    if not mismatched:
        return {"valid": True, "errors": [], "should_retry": False}

    mismatched_valid = [i for i in mismatched if 1 <= i <= len(titles)]
    if not mismatched_valid:
        return {"valid": True, "errors": [], "should_retry": False}

    errors = [f"post {i}: title '{titles[i-1]}' doesn't actually name {item_kind}" for i in mismatched_valid]
    return {
        "valid": False,
        "errors": errors,
        "should_retry": retry_count < MAX_GENERATION_RETRIES,
    }


def _collect_real_links(state: TrendForgeState) -> set:
    fetched = state.get("fetched_data", {})
    links = set()
    for items in fetched.values():
        for item in items:
            link = item.get("link", "")
            if link:
                links.add(link)
    return links


def evaluate_post_validation(state: TrendForgeState) -> Dict[str, Any]:
    posts = state.get("generated_posts", [])
    platform = state.get("platform", "instagram")
    content_intent = state.get("content_intent", "showcase")
    data_starved = state.get("data_starved", False)
    retry_count = state.get("generation_retry_count", 0)
    real_links = _collect_real_links(state)

    errors = []

    if not posts:
        errors.append("generated_posts is empty")
    else:
        max_caption_chars = PLATFORM_SETTINGS.get(platform, {}).get("max_caption_chars", 2200)
        link_required_intents = {"showcase", "news", "review"}
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

            link = post.get("link", "")
            if not data_starved and content_intent in link_required_intents and not link:
                errors.append(f"{label}: link is required for content_intent='{content_intent}' but is empty")
            elif link:
                if _is_generic_search_url(link):
                    errors.append(
                        f"{label}: link is a generic search-engine results page, not a specific source — {link}"
                    )
                elif real_links and link not in real_links:
                    errors.append(
                        f"{label}: link '{link}' was not found in the fetched source data — "
                        f"likely hallucinated, not a real source"
                    )

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