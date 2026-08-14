"""
workflow/nodes.py — thin LangGraph node wrappers

IMPORTANT (see core/state.py::state_without_reducer_keys' docstring for
the full reasoning): every node below now returns through
state_without_reducer_keys() instead of the raw `state` dict, EXCEPT
node_fetch, which is the only node that actually owns the fetched_data
channel. This isn't stylistic — LangGraph re-runs a channel's reducer
on every node return that includes that key, so returning the full
state naively from any other node silently duplicates fetched_data on
every hop. Confirmed by test, not assumed. If you add a new node here,
it needs this too, unless it's specifically responsible for writing a
reducer-owned key (see core/state.py::REDUCER_OWNED_KEYS).
"""

from core.state import TrendForgeState, add_log, state_without_reducer_keys


def node_parse(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 1 — prompt parsing, same fallback on failure."""
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
    except Exception as e:
        add_log(state, f"[Graph] Parser error: {e} — using raw prompt")
        state["core_topic"] = state["raw_prompt"][:60]
    return state_without_reducer_keys(state)


def node_route(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 2 — source routing, same fallback on failure.
    Also the target of the fetch-retry loop's back-edge — runs again on
    every retry, which is exactly why it (like every other non-fetch
    node) must not echo fetched_data back."""
    try:
        from research.routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
    except Exception as e:
        add_log(state, f"[Graph] Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]
    return state_without_reducer_keys(state)


def node_fetch(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 3 — data fetching, same two-branch fallback.

    The ONLY node allowed to return fetched_data — every other node in
    this file excludes it. See core/state.py::merge_fetched_data and
    state_without_reducer_keys for why."""
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

    return state_without_reducer_keys(state, owns=frozenset({"fetched_data"}))


def node_generate(state: TrendForgeState) -> TrendForgeState:
    """Mirrors main.py STEP 4 — content generation, same fallback on failure."""
    try:
        from generation.content_generator import ContentGenerator
        state = ContentGenerator().generate(state)
    except Exception as e:
        add_log(state, f"[Graph] Generation failed: {e}")
        state["generated_posts"] = []
    return state_without_reducer_keys(state)


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

    return state_without_reducer_keys(state)


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
        return state_without_reducer_keys(state)

    if result["should_retry"]:
        state["fetch_retry_count"] = state.get("fetch_retry_count", 0) + 1
        if result["next_query"]:
            state["fetch_summary"] = result["next_query"]
            add_log(state, f"[Graph] Fetch insufficient — retrying "
                           f"(attempt {state['fetch_retry_count']}) with query: {result['next_query']!r}")
        state["fetch_should_retry"] = True
        return state_without_reducer_keys(state)

    # Retry cap already exhausted — stop looping, proceed with whatever
    # data exists. data_starved relaxes the link requirement downstream
    # regardless of content_intent (see generation/prompts.py's link_guide
    # and workflow/gates.py's evaluate_post_validation).
    state["data_starved"] = True
    add_log(state, "[Graph] Fetch retries exhausted — proceeding with data_starved=True")
    return state_without_reducer_keys(state)


def node_evaluate_generation(state: TrendForgeState) -> TrendForgeState:
    """
    FIX (ARCHITECTURE.md graph.py Fix 1 / agents/00_graph_wiring.md):
    now calls BOTH evaluate_post_validation AND evaluate_item_kind_match
    and combines them into one retry decision. Previously only
    evaluate_post_validation ran here — ItemKindGate was built but never
    actually reachable from the graph path; only main.py's old
    procedural loop had it wired in.

    should_retry combination is OR, not AND: a retry should happen if
    EITHER gate found a real problem, even if the other gate passed
    clean. Both gates independently compute should_retry against the
    same pre-increment generation_retry_count (neither gate mutates
    state), so combining them here — before this node's own single
    increment below — can't double-count the retry budget.
    """
    from workflow.gates import evaluate_post_validation, evaluate_item_kind_match, MAX_GENERATION_RETRIES

    v1 = evaluate_post_validation(state)
    v2 = evaluate_item_kind_match(state)

    combined_errors = v1["errors"] + v2["errors"]
    combined_valid = v1["valid"] and v2["valid"]
    combined_should_retry = v1["should_retry"] or v2["should_retry"]

    state["generation_validation_errors"] = combined_errors
    state["generation_should_retry"] = False

    if combined_valid:
        add_log(state, "[Graph] Post validation + item-kind check both passed")
        return state_without_reducer_keys(state)

    if combined_should_retry:
        state["generation_retry_count"] = state.get("generation_retry_count", 0) + 1
        add_log(state, f"[Graph] Validation failed ({len(combined_errors)} issue(s): "
                       f"{len(v1['errors'])} post-validation, {len(v2['errors'])} item-kind) — "
                       f"retrying generation (attempt {state['generation_retry_count']}/{MAX_GENERATION_RETRIES})")
        state["generation_should_retry"] = True
    else:
        add_log(state, f"[Graph] Validation failed after {MAX_GENERATION_RETRIES} retries — "
                       f"proceeding with best-effort output")

    for e in combined_errors:
        add_log(state, f"[Graph]   - {e}")

    return state_without_reducer_keys(state)