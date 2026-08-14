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

import uuid

from langgraph.graph import StateGraph, START, END

from core.state import TrendForgeState, create_initial_state, get_total_tokens
from workflow.nodes import (
    node_parse, node_route, node_fetch, node_generate, node_format,
    node_evaluate_fetch, node_evaluate_generation,
)


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


def run_graph(prompt: str, platform: str = None, post_count: int = 5) -> dict:
    """
    Same 9-key return contract as main.py::run().

    FIX (ARCHITECTURE.md graph.py Fix 3): no longer wraps the graph
    invocation in its own ThreadPoolExecutor + GRAPH_TIMEOUT_SECONDS
    backstop (previously 90s). The RQ job's own job_timeout=180
    (api/web/app.py) now owns this for anything reached via the
    web/worker path — one clock, not two racing each other with
    different failure behavior.

    OBSERVATION, not silently resolved: this fix instruction assumes
    run_graph() is only ever invoked from inside the RQ worker. But per
    ARCHITECTURE.md's main.py entry, `interactive_mode` stays in
    main.py and (via orchestration/dispatch.py -> pipeline/generate.py)
    ends up calling this same run_graph() without going through RQ at
    all. That means CLI usage now has NO timeout protection if a node
    hangs (e.g. a stuck network call inside fetch), where before it had
    the 90s backstop as its ONLY one. Worth a deliberate decision:
    either main.py's CLI path needs its own timeout wrapper, or this is
    an accepted gap for CLI usage specifically. Implemented exactly as
    instructed either way — not deciding this one for you.
    """
    from Config.config import SUPPORTED_PLATFORMS

    session_id = str(uuid.uuid4())[:8]
    state = create_initial_state(raw_prompt=prompt, session_id=session_id)

    if platform and platform in SUPPORTED_PLATFORMS:
        state["platform"] = platform
    if post_count:
        state["post_count"] = post_count

    state = _compiled_graph.invoke(state)

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