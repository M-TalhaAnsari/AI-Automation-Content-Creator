"""
fetchers/github_fetcher.py — GitHub Repository Search Fetcher

Two-tier search strategy (Topics API → Keyword API), with query cleaning
and a star RANGE (not just a floor) to avoid the search always surfacing
the same handful of world-famous mega-frameworks (TensorFlow, PyTorch, etc).
The final judgment of "is this a good project idea vs a generic tool" is
left to the LLM selection step downstream (content_generator.py) — this
fetcher's job is only to supply a genuinely diverse raw candidate pool.
"""

import re
from typing import List, Dict, Any
from .base import safe_request, normalize_item, logger


def fetch_github(state, config) -> List[Dict[str, Any]]:
    """
    Fetches GitHub repositories using a two-strategy search:
    1. Topics API (tag-based match) — most precise when it works
    2. Keyword API (text match, star-range capped) — reliable fallback

    Returns an empty list (not an exception) if both strategies fail —
    the router's other selected sources (e.g. Tavily) cover the gap.
    """
    # ── GUARD 1: skip GitHub for non-tech topics or news intent ──
    category = getattr(state, "detected_category", "unknown")
    content_intent = getattr(state, "content_intent", "")
    if category not in ["tech", "unknown"] or content_intent == "news":
        logger.info(f"GitHub skipped — category={category} intent={content_intent}")
        return []

    # ── GUARD 2: topic must exist ──
    topic = getattr(state, "core_topic", None)
    if not topic:
        logger.warning("GitHub fetcher called but core_topic is missing or empty.")
        return []

    # ── Clean the topic — strip filler words that would break the search ──
    filler_pattern = r'\b(top|best|trending|latest|new|awesome|good|great|want|need|give|me|my|i|for|project|projects|repo|repos)\b'
    clean_topic = re.sub(filler_pattern, '', topic.lower())
    clean_topic = re.sub(r'\s+', ' ', clean_topic).strip()

    if not clean_topic:
        logger.warning(f"GitHub search aborted: topic '{topic}' reduced to empty string after cleaning.")
        return []

    search_url = "https://api.github.com/search/repositories"
    token = getattr(config, "GITHUB_TOKEN", None)
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    # Strategy 1: Topics API — precise tag match
    topic_tag = clean_topic.replace(' ', '-')
    params_topics = {
        "q": f"topic:{topic_tag} stars:>100",
        "sort": "stars",
        "order": "desc",
        "per_page": 10,
    }

    # Strategy 2: Keyword API — star RANGE (not just floor) so mega-frameworks
    # (which nearly always exceed 50k stars) don't structurally dominate every
    # result set, regardless of topic. Wider pool (20) gives the downstream
    # LLM selection step real variety to reason about.
    star_floor = 500 if len(clean_topic.split()) <= 3 else 100
    params_keywords = {
        "q": f"{clean_topic} stars:{star_floor}..50000",
        "sort": "stars",
        "order": "desc",
        "per_page": 20,
    }

    strategies = [
        ("Topics API", params_topics),
        ("Keyword API", params_keywords),
    ]

    for strategy_name, params in strategies:
        try:
            logger.info(f"Executing GitHub {strategy_name} with query: '{params['q']}'")
            resp = safe_request(search_url, params=params, headers=headers, timeout=15)

            if not resp:
                logger.warning(f"GitHub {strategy_name} received no response (timeout or connection error).")
                continue
            if resp.status_code != 200:
                logger.error(f"GitHub {strategy_name} returned status {resp.status_code}: {resp.text[:200]}")
                continue

            repo_items = resp.json().get("items", [])
            if not repo_items:
                logger.info(f"GitHub {strategy_name} returned 0 results — trying next strategy.")
                continue

            normalized_items = []
            for repo in repo_items:
                full_name = repo.get("full_name", "")
                description = repo.get("description") or "No description provided."
                readme_content = _fetch_readme_safe(full_name, headers)

                summary = (
                    f"{description}\n\n--- Project Details ---\n{readme_content}"
                    if readme_content else description
                )

                normalized_items.append(normalize_item(
                    title=full_name,
                    link=repo.get("html_url", ""),
                    summary=summary,
                    source="github",
                    stars=repo.get("stargazers_count", 0),
                    language=repo.get("language", ""),
                ))

            logger.info(f"GitHub {strategy_name} resolved {len(normalized_items)} items for topic '{topic}'.")
            return normalized_items

        except Exception as err:
            logger.exception(f"Unexpected error during {strategy_name}: {err}")
            continue

    logger.warning(f"All GitHub strategies exhausted for topic '{topic}'. Other sources will cover this fetch.")
    return []


def _fetch_readme_safe(full_name: str, headers: dict) -> str:
    """
    Best-effort README fetch. Returns empty string on any failure or timeout —
    a missing README should never block or slow down the overall fetch loop.
    """
    if not full_name:
        return ""
    try:
        readme_url = f"https://api.github.com/repos/{full_name}/readme"
        readme_headers = {**headers, "Accept": "application/vnd.github.v3.raw"}
        resp = safe_request(readme_url, headers=readme_headers, timeout=3)
        if resp and resp.status_code == 200:
            return resp.text[:1500].strip()
    except Exception as e:
        logger.warning(f"Failed to fetch README for {full_name}: {e}")
    return ""