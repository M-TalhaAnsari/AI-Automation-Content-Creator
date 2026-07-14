"""
workflow/graph.py — LangGraph integration (Phase 1, integration step)

Adds the fetch-quality and post-validation retry loops on top of the
Split A skeleton + Split B gates:

    START -> parse -> route -> fetch -> evaluate_fetch
                        ^                    |
                        |__ retry (cap 2) ____|
                                              | proceed
                                              v
                                          generate -> evaluate_generation
                                              ^              |
                                              |__ retry (cap 2)
                                                             | proceed
                                                             v
                                                           format -> END

Conditional-edge routing functions stay pure (read state, decide, never
mutate) — all mutation (retry counters, data_starved, next query) happens
in node_evaluate_fetch/node_evaluate_generation in workflow/nodes.py, per
gates.py's own contract that its functions never mutate state.
"""

import time
import uuid
import concurrent.futures

from langgraph.graph import StateGraph, START, END

from core.state import TrendForgeState, create_initial_state, get_total_tokens, add_error
from workflow.nodes import (
    node_parse, node_route, node_fetch, node_generate, node_format,
    node_evaluate_fetch, node_evaluate_generation,
)

GRAPH_TIMEOUT_SECONDS = 90


def _route_after_fetch_eval(state: TrendForgeState) -> str:
    """Pure routing decision — reads state, never mutates it. Trusts
    node_evaluate_fetch's own decision directly via fetch_should_retry
    rather than recomputing evaluate_fetch_quality() here (recomputation
    after the node's own retry-count increment is what caused the
    verified off-by-one/infinite-loop bugs — see workflow/nodes.py)."""
    return "retry" if state.get("fetch_should_retry") else "proceed"


def _route_after_generation_eval(state: TrendForgeState) -> str:
    """Pure routing decision, mirrors _route_after_fetch_eval's pattern —
    trusts node_evaluate_generation's generation_should_retry directly."""
    return "retry" if state.get("generation_should_retry") else "proceed"


def _build_graph():
    graph = StateGraph(TrendForgeState)

    graph.add_node("parse", node_parse)
    graph.add_node("route", node_route)
    graph.add_node("fetch", node_fetch)
    graph.add_node("evaluate_fetch", node_evaluate_fetch)
    graph.add_node("generate", node_generate)
    graph.add_node("evaluate_generation", node_evaluate_generation)
    graph.add_node("format", node_format)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "route")
    graph.add_edge("route", "fetch")
    graph.add_edge("fetch", "evaluate_fetch")

    graph.add_conditional_edges(
        "evaluate_fetch",
        _route_after_fetch_eval,
        {"proceed": "generate", "retry": "route"},
    )

    graph.add_edge("generate", "evaluate_generation")

    graph.add_conditional_edges(
        "evaluate_generation",
        _route_after_generation_eval,
        {"proceed": "format", "retry": "generate"},
    )

    graph.add_edge("format", END)

    return graph.compile()


_compiled_graph = _build_graph()


def _timeout_fallback(state: TrendForgeState, session_id: str, elapsed: float) -> dict:
    """
    Built when the whole graph run exceeds GRAPH_TIMEOUT_SECONDS. This is
    a backstop that bounds the CALLER's wait time, not a true mid-execution
    cancellation — the underlying thread (likely blocked on a network call
    inside a node) keeps running orphaned in the background, since Python
    can't safely force-kill a thread stuck in a blocking call. A real
    cooperative-cancellation model (checking a deadline between each node)
    would be needed for genuine partial-state recovery; that's a larger
    change than this phase's backstop requirement calls for. Flagging this
    limitation explicitly rather than presenting it as more than it is.
    """
    fallback_state = create_initial_state(raw_prompt=state.get("raw_prompt", ""), session_id=session_id)
    add_error(fallback_state, f"[Graph] Timed out after {elapsed:.1f}s (limit {GRAPH_TIMEOUT_SECONDS}s) — no output produced")
    return {
        "output": "",
        "session_id": session_id,
        "tokens": fallback_state["tokens"],
        "total_tokens": 0,
        "errors": fallback_state["errors"],
        "posts": [],
        "topic": state.get("core_topic", ""),
        "platform": state.get("platform", ""),
        "content_intent": state.get("content_intent", ""),
    }


def run_graph(prompt: str, platform: str = None, post_count: int = 5) -> dict:
    """
    Same 9-key return contract as main.py::run() (verified against the
    live file — see workflow/graph.py's original Split A docstring for
    the full field-by-field mapping). Now includes the fetch-quality and
    post-validation retry loops, plus a wall-clock timeout backstop.
    """
    from config import SUPPORTED_PLATFORMS

    session_id = str(uuid.uuid4())[:8]
    state = create_initial_state(raw_prompt=prompt, session_id=session_id)

    if platform and platform in SUPPORTED_PLATFORMS:
        state["platform"] = platform
    if post_count:
        state["post_count"] = post_count

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_compiled_graph.invoke, state)
        try:
            state = future.result(timeout=GRAPH_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            elapsed = time.time() - start
            return _timeout_fallback(state, session_id, elapsed)

    return {
        "output":     state["final_output"],
        "session_id": session_id,
        "tokens":     state["tokens"],
        "total_tokens": get_total_tokens(state),
        "errors":     state["errors"],
        "posts":      state["generated_posts"],
        "topic":      state.get("core_topic", ""),
        "platform":   state.get("platform", ""),
        "content_intent": state.get("content_intent", ""),
    }