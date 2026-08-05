"""
fetchers/paperswithcode_fetcher.py — Research Paper Fetcher

Uses Hugging Face's Papers API (the original Papers With Code API was
discontinued in July 2025; Hugging Face now maintains the closest
equivalent). Falls back to trending papers, then to Tavily, if the
topic search returns nothing.

Only useful for research-oriented requests — the router should only
select this source when special_requests includes "research", and
this fetcher enforces that itself as a safety net.
"""

from typing import List, Dict, Any
from .base import logger, normalize_item
import requests

HF_PAPERS_SEARCH = "https://huggingface.co/api/papers/search"
HF_PAPERS_TRENDING = "https://huggingface.co/api/papers/trending"


def _extract_papers(data) -> list:
    """Normalizes the various shapes HF's API can return into a flat list of paper dicts."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        papers = data.get("papers", data.get("results", []))
        if isinstance(papers, dict):
            papers = papers.get("papers", [])
        return papers if isinstance(papers, list) else []
    return []


def _paper_to_item(paper: dict) -> Dict[str, Any]:
    """Converts one raw HF paper dict into a normalized fetch item. Shared by both search and trending paths."""
    title = paper.get("title", "")
    paper_id = paper.get("id", paper.get("paperId", ""))
    abstract = paper.get("summary", paper.get("abstract", ""))

    authors = paper.get("authors", [])
    if isinstance(authors, list):
        author = ", ".join(a.get("name", "") for a in authors if isinstance(a, dict))[:200]
    else:
        author = str(authors) if authors else ""

    url = paper.get("url") or (f"https://huggingface.co/papers/{paper_id}" if paper_id else "")

    return normalize_item(
        title=title,
        link=url or f"https://paperswithcode.co/paper/{title.replace(' ', '-').lower()}",
        summary=abstract[:300] if abstract else "Paper on Hugging Face Papers.",
        source="paperswithcode",
        stars=paper.get("upvotes", paper.get("stars", 0)),
        author=author,
        published=paper.get("publishedAt", paper.get("published", "")),
    )


def _tavily_paper_fallback(topic: str, config) -> List[Dict[str, Any]]:
    """Last-resort fallback: search Tavily for papers about the topic."""
    if not (hasattr(config, "TAVILY_API_KEY") and config.TAVILY_API_KEY):
        return []

    try:
        from .tavily_fetcher import fetch_tavily

        class _PaperSearchState:
            """Minimal object satisfying fetch_tavily's expected interface. Local to this fallback only."""
            core_topic = f"{topic} research papers"
            search_queries = [f"{topic} research papers"]

        results = fetch_tavily(_PaperSearchState(), config)
        return [
            normalize_item(
                title=r.get("title", ""),
                link=r.get("link", ""),
                summary=r.get("summary", ""),
                source="tavily_papers",
            )
            for r in results[:5]
        ]
    except Exception as e:
        logger.warning(f"Tavily paper fallback failed: {e}")
        return []


def fetch_paperswithcode(state, config) -> List[Dict[str, Any]]:
    """
    Fetches research papers relevant to core_topic.
    Only intended for research-oriented requests — see module docstring.
    """
    special_requests = getattr(state, "special_requests", [])
    if "research" not in special_requests:
        logger.info("PapersWithCode skipped — 'research' not in special_requests.")
        return []

    topic = getattr(state, "core_topic", "")
    items: List[Dict[str, Any]] = []

    # ── Attempt 1: topic-specific search ──
    if topic:
        try:
            response = requests.get(HF_PAPERS_SEARCH, params={"q": topic, "limit": 10}, timeout=15)
            if response.status_code == 200:
                papers = _extract_papers(response.json())
                items = [_paper_to_item(p) for p in papers[:10] if isinstance(p, dict) and p.get("title")]
                if items:
                    logger.info(f"HF Papers search returned {len(items)} items for '{topic}'.")
                    return items
        except Exception as e:
            logger.warning(f"HF Papers search failed: {e}")

    # ── Attempt 2: trending papers (topic search returned nothing) ──
    try:
        response = requests.get(HF_PAPERS_TRENDING, timeout=15)
        if response.status_code == 200:
            papers = _extract_papers(response.json())
            items = [_paper_to_item(p) for p in papers[:10] if isinstance(p, dict) and p.get("title")]
            if items:
                logger.info(f"HF Papers trending returned {len(items)} items.")
                return items
    except Exception as e:
        logger.warning(f"HF Papers trending fetch failed: {e}")

    # ── Attempt 3: Tavily fallback ──
    items = _tavily_paper_fallback(topic, config)
    logger.info(f"PapersWithCode fetch complete — {len(items)} items (via fallback chain).")
    return items