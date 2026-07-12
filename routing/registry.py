"""
routing/registry.py — Source Registry

THE single source of truth for every data source in TrendForge.

To add a new source in the future:
    1. Create fetchers/your_source_fetcher.py
    2. Add a SourceMetadata entry here
    3. Done — router, status display, and pipeline all pick it up automatically

No other file needs to change.

This file answers:
    - What sources exist?
    - Which categories does each source serve?
    - Which sources need API keys?
    - Which sources are available right now (based on .env)?
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from routing.base import SourceMetadata
from config import CONFIG


# ═══════════════════════════════════════════════════════
# SOURCE REGISTRY
# Add new sources here — nothing else needs to change
# ═══════════════════════════════════════════════════════

ALL_SOURCES: Dict[str, SourceMetadata] = {

    "github": SourceMetadata(
        name="github",
        display_name="GitHub Trending",
        description="Most starred repos this week — real trending projects with links",
        categories=["tech"],
        requires_key=False,
        key_env_var="GITHUB_TOKEN",         # optional — increases rate limit
        rate_limit="60 req/hour (no token) | 5000 req/hour (with token)",
        data_freshness="daily",
        fetcher_module="fetchers.github_fetcher",
        fetcher_class="GitHubFetcher",
    ),

    "hackernews": SourceMetadata(
        name="hackernews",
        display_name="Hacker News",
        description="Top tech stories voted by developer community right now",
        categories=[ "business", "education"],
        requires_key=False,
        key_env_var=None,
        rate_limit="unlimited",
        data_freshness="real-time",
        fetcher_module="fetchers.hackernews_fetcher",
        fetcher_class="HackerNewsFetcher",
    ),

    "paperswithcode": SourceMetadata(
        name="paperswithcode",
        display_name="Papers With Code",
        description="Latest ML research papers with GitHub implementations",
        categories=["tech"],
        requires_key=False,
        key_env_var=None,
        rate_limit="unlimited",
        data_freshness="real-time",
        fetcher_module="fetchers.paperswithcode_fetcher",
        fetcher_class="PapersWithCodeFetcher",
    ),

    "huggingface": SourceMetadata(
        name="huggingface",
        display_name="Hugging Face Trending",
        description="Most downloaded AI models and spaces this week",
        categories=["tech"],
        requires_key=False,
        key_env_var=None,
        rate_limit="unlimited",
        data_freshness="daily",
        fetcher_module="fetchers.huggingface_fetcher",
        fetcher_class="HuggingFaceFetcher",
    ),

    "google_trends": SourceMetadata(
        name="google_trends",
        display_name="Google Trends",
        description="What people are searching for RIGHT NOW — works for any topic",
        categories=["tech", "business", "lifestyle", "entertainment", "education", "unknown"],
        requires_key=False,
        key_env_var=None,
        rate_limit="~100 req/hour (unofficial)",
        data_freshness="real-time",
        fetcher_module="fetchers.google_trends_fetcher",
        fetcher_class="GoogleTrendsFetcher",
    ),

    "reddit": SourceMetadata(
        name="reddit",
        display_name="Reddit",
        description="Hot posts from relevant subreddits — real community opinions",
        categories=["tech", "business", "lifestyle", "entertainment", "education", "unknown"],
        requires_key=True,
        key_env_var="REDDIT_CLIENT_ID",
        rate_limit="60 req/minute",
        data_freshness="real-time",
        fetcher_module="fetchers.reddit_fetcher",
        fetcher_class="RedditFetcher",
    ),

    "youtube": SourceMetadata(
        name="youtube",
        display_name="YouTube Trending",
        description="Trending videos in the topic category — real view counts",
        categories=["lifestyle", "entertainment", "education", "unknown"],
        requires_key=True,
        key_env_var="YOUTUBE_API_KEY",
        rate_limit="10,000 units/day",
        data_freshness="daily",
        fetcher_module="fetchers.youtube_fetcher",
        fetcher_class="YouTubeFetcher",
    ),

    "tavily": SourceMetadata(
        name="tavily",
        display_name="Tavily Web Search",
        description="Live web search fallback — finds anything not covered by other sources",
        categories=["tech", "business", "lifestyle", "entertainment", "education", "unknown"],
        requires_key=True,
        key_env_var="TAVILY_API_KEY",
        rate_limit="1000 req/month (free tier)",
        data_freshness="real-time",
        fetcher_module="fetchers.tavily_fetcher",
        fetcher_class="TavilyFetcher",
    ),

    # ── FUTURE SOURCES — uncomment when ready ──────────────────
    # "producthunt": SourceMetadata(
    #     name="producthunt",
    #     display_name="Product Hunt",
    #     description="New AI tools and products launching today",
    #     categories=["tech", "business"],
    #     requires_key=True,
    #     key_env_var="PRODUCTHUNT_API_KEY",
    #     rate_limit="500 req/hour",
    #     data_freshness="daily",
    #     fetcher_module="fetchers.producthunt_fetcher",
    #     fetcher_class="ProductHuntFetcher",
    # ),
    #
    # "spotify": SourceMetadata(
    #     name="spotify",
    #     display_name="Spotify Charts",
    #     description="Trending music and podcast topics",
    #     categories=["entertainment", "lifestyle"],
    #     requires_key=True,
    #     key_env_var="SPOTIFY_CLIENT_ID",
    #     rate_limit="generous",
    #     data_freshness="daily",
    #     fetcher_module="fetchers.spotify_fetcher",
    #     fetcher_class="SpotifyFetcher",
    # ),
    #
    # "arxiv": SourceMetadata(
    #     name="arxiv",
    #     display_name="arXiv Papers",
    #     description="Brand new research papers — bleeding edge before GitHub",
    #     categories=["tech"],
    #     requires_key=False,
    #     key_env_var=None,
    #     rate_limit="3 req/second",
    #     data_freshness="real-time",
    #     fetcher_module="fetchers.arxiv_fetcher",
    #     fetcher_class="ArxivFetcher",
    # ),
}


# ═══════════════════════════════════════════════════════
# REGISTRY QUERY FUNCTIONS
# Used by routers, status display, and pipeline
# ═══════════════════════════════════════════════════════

def get_all_source_names() -> List[str]:
    """Returns names of all registered sources."""
    return list(ALL_SOURCES.keys())


def get_source(name: str) -> Optional[SourceMetadata]:
    """Returns metadata for a specific source."""
    return ALL_SOURCES.get(name)


def get_sources_for_category(category: str) -> List[str]:
    """Returns source names that serve a given category."""
    return [
        name for name, meta in ALL_SOURCES.items()
        if category in meta.categories
    ]


def get_available_sources() -> List[str]:
    """
    Returns sources that are actually usable right now.
    Checks: enabled in config + API key present if required.
    This is the authoritative list — routers use this to filter.
    """
    available = []
    s = CONFIG.sources

    # Sources that need no key — always available if enabled
    no_key_sources = {
        "github":         s.enable_github,
        "hackernews":     s.enable_hackernews,
        "paperswithcode": s.enable_paperswithcode,
        "huggingface":    s.enable_huggingface,
        "google_trends":  s.enable_google_trends,
    }
    for source_name, is_enabled in no_key_sources.items():
        if is_enabled:
            available.append(source_name)

    # Sources that need keys
    keyed_sources = {
        "reddit":  (s.enable_reddit, s.reddit_client_id),
        "youtube": (s.enable_youtube, s.youtube_api_key),
        "tavily":  (s.enable_tavily, s.tavily_api_key),
    }
    for source_name, (is_enabled, key) in keyed_sources.items():
        if is_enabled and key:
            available.append(source_name)

    return available


def get_source_display_info() -> List[Dict]:
    """
    Returns display info for all sources — used by status printer.
    Includes availability status.
    """
    available = get_available_sources()
    result = []
    for name, meta in ALL_SOURCES.items():
        result.append({
            "name": name,
            "display_name": meta.display_name,
            "description": meta.description,
            "available": name in available,
            "requires_key": meta.requires_key,
            "key_env_var": meta.key_env_var,
            "freshness": meta.data_freshness,
        })
    return result
