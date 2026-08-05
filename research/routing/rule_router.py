"""
routing/rule_router.py — Rule-Based Source Router (0 tokens)

Selects data sources using the category → source mapping in config.py.
Fast, free, handles the majority of cases correctly since IntentExtractor
already does the hard semantic work of deciding the category.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from research.routing.base import BaseRouter
from research.routing.registry import get_available_sources
from core.state import TrendForgeState, add_log
from config import SOURCE_MAP


class RuleRouter(BaseRouter):

    @property
    def name(self) -> str:
        return "rules"

    def can_handle(self, state: TrendForgeState) -> bool:
        """Can handle if IntentExtractor already assigned a real category."""
        return state.get("detected_category", "unknown") != "unknown"

    def select_sources(self, state: TrendForgeState) -> List[str]:
        category = state.get("detected_category", "unknown")
        available = get_available_sources()
        special = state.get("special_requests", [])   # read once, used throughout

        wanted = list(SOURCE_MAP.get(category, SOURCE_MAP["unknown"]))

        # paperswithcode returns academic papers — only relevant if the user
        # explicitly asked for research/papers, otherwise it's noise for a
        # general "show me projects" request.
        if "paperswithcode" in wanted and "research" not in special:
            wanted.remove("paperswithcode")

        # tavily is always a safe fallback source when available
        if "tavily" in available and "tavily" not in wanted:
            wanted.append("tavily")

        selected = self.validate_sources(wanted, available)

        # Explicit special-request overrides — these always win regardless
        # of what the category mapping produced.
        if "github_links" in special and "github" in available and "github" not in selected:
            selected.insert(0, "github")
        if "trending_only" in special and "google_trends" in available and "google_trends" not in selected:
            selected.append("google_trends")

        add_log(state, f"[RuleRouter] category={category} → sources={selected}")
        return selected