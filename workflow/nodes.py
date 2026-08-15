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
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
    except Exception as e:
        add_log(state, f"[Graph] Parser error: {e} — using raw prompt")
        state["core_topic"] = state["raw_prompt"][:60]
    return state_without_reducer_keys(state)


def node_route(state: TrendForgeState) -> TrendForgeState:
    try:
        from research.routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
    except Exception as e:
        add_log(state, f"[Graph] Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]
    return state_without_reducer_keys(state)


def node_fetch(state: TrendForgeState) -> TrendForgeState:
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
    try:
        from generation.content_generator import ContentGenerator
        state = ContentGenerator().generate(state)
    except Exception as e:
        add_log(state, f"[Graph] Generation failed: {e}")
        state["generated_posts"] = []
    return state_without_reducer_keys(state)


def node_format(state: TrendForgeState) -> TrendForgeState:
    from generation.formatter import format_output, save_output
    state = format_output(state)
    save_output(state)

    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        add_log(state, f"[Graph] Session history save failed: {e}")

    return state_without_reducer_keys(state)


def node_evaluate_fetch(state: TrendForgeState) -> TrendForgeState:
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

    state["data_starved"] = True
    add_log(state, "[Graph] Fetch retries exhausted — proceeding with data_starved=True")
    return state_without_reducer_keys(state)


def node_evaluate_generation(state: TrendForgeState) -> TrendForgeState:
    """
    FIX (this session): the OR-combination logic previously lived only
    here, inline. Extracted to workflow.gates.evaluate_generation_combined
    so orchestration/dispatch.py's generate_more/targeted_refetch retry
    loop (added to close the validation-gate gap documented in
    CLAUDE.md) shares this exact logic instead of a second hand-written
    copy. Log output and retry-count behavior are unchanged.
    """
    from workflow.gates import evaluate_generation_combined, MAX_GENERATION_RETRIES

    result = evaluate_generation_combined(state)
    state["generation_validation_errors"] = result["errors"]
    state["generation_should_retry"] = False

    if result["valid"]:
        add_log(state, "[Graph] Post validation + item-kind check both passed")
        return state_without_reducer_keys(state)

    if result["should_retry"]:
        state["generation_retry_count"] = state.get("generation_retry_count", 0) + 1
        add_log(state, f"[Graph] Validation failed ({len(result['errors'])} issue(s): "
                       f"{len(result['post_validation_errors'])} post-validation, "
                       f"{len(result['item_kind_errors'])} item-kind) — "
                       f"retrying generation (attempt {state['generation_retry_count']}/{MAX_GENERATION_RETRIES})")
        state["generation_should_retry"] = True
    else:
        add_log(state, f"[Graph] Validation failed after {MAX_GENERATION_RETRIES} retries — "
                       f"proceeding with best-effort output")

    for e in result["errors"]:
        add_log(state, f"[Graph]   - {e}")

    return state_without_reducer_keys(state)