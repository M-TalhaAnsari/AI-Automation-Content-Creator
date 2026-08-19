"""
fetchers/fetcher_orchestrator.py — Data Fetching Coordinator

Runs each selected source's fetcher function, passing it the real
pipeline state (as produced by intent_extractor.py). Does NOT
reinterpret or rewrite the topic/search queries here — that reasoning
already happened once, correctly, in the understanding layer. This
file's only job is dispatch: for each selected source, call its
fetcher and collect results.
"""

import concurrent.futures
import logging
import types
from typing import Dict, Any, List, Tuple

from .github_fetcher import fetch_github
from .hackernews_fetcher import fetch_hackernews
from .youtube_fetcher import fetch_youtube
from .google_trends_fetcher import fetch_google_trends
from .paperswithcode_fetcher import fetch_paperswithcode
from .tavily_fetcher import fetch_tavily
from .fetching_reddit.reddit_fetcher import fetch_reddit

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
        """Runs fetchers concurrently for every source in state['selected_sources']. Never raises."""
        selected = state.get("selected_sources", [])
        if not selected:
            logger.info("No sources selected, skipping fetch.")
            state["fetched_data"] = {}
            state["total_items_fetched"] = state.get("total_items_fetched", 0)
            state["sources_used"] = state.get("sources_used", [])
            return state

        # Pass the REAL state through unchanged — intent_extractor.py already
        # decided core_topic, search_queries, category, content_intent, etc.
        # correctly. Fetchers read what they need via getattr with sensible
        # fallbacks (see tavily_fetcher.py for the pattern).
        state_obj = types.SimpleNamespace(**state)

        from Config.config import CONFIG

        fetched: Dict[str, list] = {}
        total_items = 0
        sources_used = []

        valid_sources = [s for s in selected if s in FETCHER_MAP]
        for s in selected:
            if s not in FETCHER_MAP:
                logger.warning(f"No fetcher registered for source: {s}")

        if not valid_sources:
            state["fetched_data"] = {}
            state["total_items_fetched"] = state.get("total_items_fetched", 0)
            state["sources_used"] = state.get("sources_used", [])
            return state

        def _fetch_single_source(source: str) -> Tuple[str, List[Dict[str, Any]], str | None]:
            fetcher = FETCHER_MAP[source]
            try:
                items = fetcher(state_obj, CONFIG)
                return source, items or [], None
            except Exception as e:
                return source, [], str(e)

        # Concurrently fan out independent HTTP fetch calls across threads
        max_workers = min(len(valid_sources), 6)
        results_by_source: Dict[str, Tuple[List[Dict[str, Any]], str | None]] = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(_fetch_single_source, src): src for src in valid_sources
            }
            for future in concurrent.futures.as_completed(future_to_source):
                src, items, err = future.result()
                results_by_source[src] = (items, err)

        # Reconstruct output in the deterministic order specified by state['selected_sources']
        for source in selected:
            if source not in results_by_source:
                continue
            items, err = results_by_source[source]
            fetched[source] = items
            if err:
                logger.error(f"Error fetching from {source}: {err}")
                state.setdefault("errors", []).append(f"Source [{source}] execution failure: {err}")
            else:
                if items:
                    sources_used.append(source)
                    total_items += len(items)
                logger.info(f"Fetched {len(items)} items from {source}")

        state["fetched_data"] = fetched
        # Accumulate across retries (LangGraph reducer merges fetched_data;
        # total_items_fetched and sources_used accumulate manually).
        state["total_items_fetched"] = state.get("total_items_fetched", 0) + total_items
        # dict.fromkeys preserves insertion order while deduplicating across retries.
        state["sources_used"] = list(dict.fromkeys(state.get("sources_used", []) + sources_used))
        return state