"""
workflow/nodes.py — thin LangGraph node wrappers

Each node mirrors the exact try/except graceful-degradation behavior
main.py::run() has today, stage for stage. No new logic, no gates, no
retries — that's added in the later integration step (see the Phase 1
master reference, §4).
"""

from core.state import TrendForgeState, add_log


def node_parse(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 1 — prompt parsing, same fallback on failure."""
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
    except Exception as e:
        add_log(state, f"[Graph] Parser error: {e} — using raw prompt")
        state["core_topic"] = state["raw_prompt"][:60]
    return state


def node_route(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 2 — source routing, same fallback on failure."""
    try:
        from routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
    except Exception as e:
        add_log(state, f"[Graph] Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]
    return state


def node_fetch(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 3 — data fetching, same two-branch fallback."""
    try:
        from fetchers.fetcher_orchestrator import FetcherOrchestrator
        state = FetcherOrchestrator().fetch(state)
    except ImportError:
        state["fetched_data"] = {}
        state["total_items_fetched"] = 0
        state["sources_used"] = []
        add_log(state, "[Graph] Fetchers not found — Gemini uses training knowledge")
    except Exception as e:
        state["fetched_data"] = {}
        state["total_items_fetched"] = 0
        state["sources_used"] = []
        add_log(state, f"[Graph] Fetch error: {e} — continuing without live data")

    # Mirrors main.py's already-covered lookup, which runs right after
    # fetching and before generation in the current linear pipeline.
    try:
        from memory.session_store import get_already_covered
        state["already_covered"] = get_already_covered(state["core_topic"], state["platform"])
        if state["already_covered"]:
            add_log(state, f"[Graph] Found {len(state['already_covered'])} previously-covered items for this topic/platform")
    except Exception as e:
        state["already_covered"] = []
        add_log(state, f"[Graph] Already-covered lookup skipped: {e}")

    return state


def node_generate(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 4 — content generation, same fallback on failure."""
    try:
        from generation.content_generator import ContentGenerator
        state = ContentGenerator().generate(state)
    except Exception as e:
        add_log(state, f"[Graph] Generation failed: {e}")
        state["generated_posts"] = []
    return state


def node_format(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 5 — formatting, saving output, and session history.
    Unlike the other stages, main.py does not wrap this stage's own call in
    a try/except (format_output/save_output are called directly) — mirrored
    here exactly, no extra error handling added that main.py doesn't have.
    save_output's return value (the saved path) is not part of the 9-key
    return contract in main.py::run() either, so it's called only for its
    side effect here, not stored on state — avoids adding an undocumented
    field to the schema for something the contract never exposed anyway."""
    from generation.formatter import format_output, save_output
    state = format_output(state)
    save_output(state)

    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        add_log(state, f"[Graph] Session history save failed: {e}")

    return state