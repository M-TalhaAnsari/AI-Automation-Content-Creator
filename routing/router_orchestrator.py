"""
routing/router_orchestrator.py — Router Orchestrator (Step 3 Entry Point)

Tries routers in priority order:
  1. RuleRouter  (0 tokens) — if confident
  2. LLMRouter   (~100 tokens) — if rules uncertain

To add a new router strategy in future:
  1. Create class extending BaseRouter
  2. Add to ROUTER_CHAIN list below
  Done.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from routing.rule_router import RuleRouter
from routing.llm_router import LLMRouter
from routing.registry import get_available_sources
from core.state import TrendForgeState, add_log, add_error


# Priority order — first router that can_handle() wins
ROUTER_CHAIN = [
    RuleRouter(),
    LLMRouter(),
]


class RouterOrchestrator:
    """
    Runs routers in chain order.
    First confident router wins.
    LLMRouter always handles as final fallback.
    """

    def route(self, state: TrendForgeState) -> TrendForgeState:
        add_log(state, "[Router] Starting source selection...")

        available = get_available_sources()
        add_log(state, f"[Router] Available sources: {available}")

        if not available:
            add_error(state, "[Router] No sources available — check API keys in .env")
            state["selected_sources"] = []
            state["routing_method"] = "none"
            return state

        selected: List[str] = []
        method_used = ""

        for router in ROUTER_CHAIN:
            if router.can_handle(state):
                add_log(state, f"[Router] Trying {router.name} router...")
                selected = router.select_sources(state)
                if selected:
                    method_used = router.name
                    break

        # If nothing worked, prefer general-purpose sources
        if not selected:
            general = ["google_trends", "reddit", "tavily"]
            selected = [s for s in general if s in available] or available[:4]
            method_used = "fallback_general"
            add_log(state, f"[Router] Using general fallback sources: {selected}")

        state["selected_sources"] = selected
        state["routing_method"] = method_used

        add_log(state, f"[Router] ✓ Final sources={selected} via method={method_used}")
        return state
