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
        from research.routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
    except Exception as e:
        add_log(state, f"[Graph] Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]
    return state


def node_fetch(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 3 — data fetching, same two-branch fallback."""
    try:
        from research.fetchers.fetcher_orchestrator import FetcherOrchestrator
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


# ── Phase 1 integration: evaluation nodes ──────────────────────────
# These call the pure functions in workflow/gates.py and apply their
# result to state (retry counters, data_starved, next query). gates.py
# itself never mutates state — that contract stays intact; this is the
# orchestration layer that acts on what the gates decide.

def node_evaluate_fetch(state: TrendForgeState) -> TrendForgeState:
    """After fetch — decides whether to proceed to generation or loop
    back to routing with a different search query. Sets fetch_should_retry
    explicitly so the router never has to recompute this decision."""
    from workflow.gates import evaluate_fetch_quality

    result = evaluate_fetch_quality(state)
    add_log(state, f"[Graph] Fetch quality check: {result['reason']}")
    state["fetch_should_retry"] = False

    if result["sufficient"]:
        return state

    if result["should_retry"]:
        state["fetch_retry_count"] = state.get("fetch_retry_count", 0) + 1
        if result["next_query"]:
            state["fetch_summary"] = result["next_query"]
            add_log(state, f"[Graph] Fetch insufficient — retrying "
                           f"(attempt {state['fetch_retry_count']}) with query: {result['next_query']!r}")
        state["fetch_should_retry"] = True
        return state

    # Retry cap already exhausted — stop looping, proceed with whatever
    # data exists. data_starved relaxes the link requirement downstream
    # regardless of content_intent (see generation/prompts.py's link_guide
    # and workflow/gates.py's evaluate_post_validation).
    state["data_starved"] = True
    add_log(state, "[Graph] Fetch retries exhausted — proceeding with data_starved=True")
    return state


def node_evaluate_generation(state: TrendForgeState) -> TrendForgeState:
    """After generation — decides whether to proceed to formatting or
    regenerate the batch. Sets generation_should_retry explicitly, computed
    once here using the correct pre-increment retry count — the router
    reads this directly and never recomputes it. Recomputing after this
    node's own increment produced a verified off-by-one bug: it cut the
    retry loop short by one attempt, and the naive alternate fix (using a
    different comparison operator) caused an infinite loop instead, in the
    case where generation is still invalid on the final allowed attempt —
    a frozen retry-count integer alone can't distinguish "just approved
    this retry" from "already gave up" once it stops changing."""
    from workflow.gates import evaluate_post_validation, MAX_GENERATION_RETRIES

    result = evaluate_post_validation(state)
    state["generation_validation_errors"] = result["errors"]
    state["generation_should_retry"] = False

    if result["valid"]:
        add_log(state, "[Graph] Post validation passed")
        return state

    if result["should_retry"]:
        state["generation_retry_count"] = state.get("generation_retry_count", 0) + 1
        add_log(state, f"[Graph] Post validation failed ({len(result['errors'])} issue(s)) — "
                       f"retrying generation (attempt {state['generation_retry_count']}/{MAX_GENERATION_RETRIES})")
        state["generation_should_retry"] = True
    else:
        add_log(state, f"[Graph] Post validation failed after {MAX_GENERATION_RETRIES} retries — "
                       f"proceeding with best-effort output")

    for e in result["errors"]:
        add_log(state, f"[Graph]   - {e}")

    return state