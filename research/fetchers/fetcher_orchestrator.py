"""
fetchers/fetcher_orchestrator.py — Data Fetching Coordinator

Runs each selected source's fetcher function, passing it the real
pipeline state (as produced by intent_extractor.py). Does NOT
reinterpret or rewrite the topic/search queries here — that reasoning
already happened once, correctly, in the understanding layer. This
file's only job is dispatch: for each selected source, call its
fetcher and collect results.
"""

import logging
import types
from typing import Dict, Any

from .github_fetcher import fetch_github
from .hackernews_fetcher import fetch_hackernews
from .youtube_fetcher import fetch_youtube
from .google_trends_fetcher import fetch_google_trends
from .paperswithcode_fetcher import fetch_paperswithcode
from .tavily_fetcher import fetch_tavily
from .fetching_reddit.reddit_fetcher import fetch_reddit  # confirm this path matches your actual folder layout

logger = logging.getLogger("trendforge.fetchers.orchestrator")

FETCHER_MAP = {
    "github": fetch_github,
    "hackernews": fetch_hackernews,
    "youtube": fetch_youtube,
    "google_trends": fetch_google_trends,
    "paperswithcode": fetch_paperswithcode,
    "tavily": fetch_tavily,
    "reddit": fetch_reddit,
}


class FetcherOrchestrator:
    def fetch(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs fetchers for every source in state['selected_sources']. Never raises."""
        selected = state.get("selected_sources", [])
        if not selected:
            logger.info("No sources selected, skipping fetch.")
            state["fetched_data"] = {}
            state["total_items_fetched"] = 0
            state["sources_used"] = []
            return state

        # Pass the REAL state through unchanged — intent_extractor.py already
        # decided core_topic, search_queries, category, content_intent, etc.
        # correctly. Fetchers read what they need via getattr with sensible
        # fallbacks (see tavily_fetcher.py for the pattern).
        state_obj = types.SimpleNamespace(**state)

        fetched: Dict[str, list] = {}
        total_items = 0
        sources_used = []

        from Config.config import CONFIG

        for source in selected:
            fetcher = FETCHER_MAP.get(source)
            if not fetcher:
                logger.warning(f"No fetcher registered for source: {source}")
                continue

            try:
                items = fetcher(state_obj, CONFIG)
                fetched[source] = items
                if items:
                    sources_used.append(source)
                    total_items += len(items)
                logger.info(f"Fetched {len(items)} items from {source}")

            except Exception as e:
                logger.error(f"Error fetching from {source}: {e}")
                fetched[source] = []
                state.setdefault("errors", []).append(f"Source [{source}] execution failure: {e}")

        state["fetched_data"] = fetched
        # FIX (Bug 4): total_items_fetched and sources_used were flat-overwritten
        # on every call. fetched_data is reducer-merged across retries (by
        # LangGraph's merge_fetched_data); these two companion fields must
        # accumulate manually to stay consistent. Without this, after any fetch
        # retry they reflect only the last attempt's numbers, not the cumulative
        # total — causing formatter/API response to show an undercount.
        state["total_items_fetched"] = state.get("total_items_fetched", 0) + total_items
        # dict.fromkeys preserves insertion order while deduplicating across retries.
        state["sources_used"] = list(dict.fromkeys(state.get("sources_used", []) + sources_used))
        return state