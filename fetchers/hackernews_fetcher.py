"""
fetchers/hackernews_fetcher.py — Hacker News Search Fetcher

Uses the official Algolia-backed HN Search API (hn.algolia.com) to find
stories matching core_topic — NOT the raw front-page firehose, which
always returns the same ~15 globally trending stories regardless of
topic and was pure noise for content generation.
"""

from typing import List, Dict, Any
from .base import safe_request, normalize_item, logger

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def fetch_hackernews(state, config) -> List[Dict[str, Any]]:
    """
    Searches Hacker News for stories matching core_topic.
    Returns an empty list if no topic is available — this source has
    nothing relevant to contribute without something to search for.
    """
    topic = getattr(state, "core_topic", "")
    items: List[Dict[str, Any]] = []

    if not topic:
        logger.info("No topic provided; skipping Hacker News.")
        return items

    params = {
        "query": topic,
        "tags": "story",
        "hitsPerPage": 15,
    }

    resp = safe_request(HN_SEARCH_URL, params=params, timeout=10)
    if not resp:
        logger.error("Hacker News search endpoint failed.")
        return items

    try:
        hits = resp.json().get("hits", [])
    except Exception:
        logger.error("Failed to parse Hacker News search response.")
        return items

    for hit in hits:
        title = hit.get("title", "")
        if not title:
            continue
        object_id = hit.get("objectID", "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"

        items.append(normalize_item(
            title=title,
            link=url,
            summary=(hit.get("story_text") or "")[:200] or "Hacker News story.",
            source="hackernews",
            score=hit.get("points", 0),
            author=hit.get("author", ""),
        ))

    logger.info(f"Hacker News returned {len(items)} items matching '{topic}'.")
    return items