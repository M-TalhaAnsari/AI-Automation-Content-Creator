"""
workflow/graph.py — LangGraph skeleton wrap (Phase 1, Split A)

Linear mirror of main.py::run() — zero behavior change, no gates, no
retries. This is an additive parallel path only; main.py is untouched
and still the live entry point until an explicit later integration step.

Graph shape: START -> parse -> route -> fetch -> generate -> format -> END
"""

import uuid
from langgraph.graph import StateGraph, START, END

from core.state import TrendForgeState, create_initial_state, get_total_tokens
from workflow.nodes import node_parse, node_route, node_fetch, node_generate, node_format


def _build_graph():
    graph = StateGraph(TrendForgeState)

    graph.add_node("parse", node_parse)
    graph.add_node("route", node_route)
    graph.add_node("fetch", node_fetch)
    graph.add_node("generate", node_generate)
    graph.add_node("format", node_format)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "route")
    graph.add_edge("route", "fetch")
    graph.add_edge("fetch", "generate")
    graph.add_edge("generate", "format")
    graph.add_edge("format", END)

    return graph.compile()


_compiled_graph = _build_graph()


def run_graph(prompt: str, platform: str = None, post_count: int = 5) -> dict:
    """
    Same return contract as main.py::run() — verified against the live
    file, 9 keys, not the 6-key shape from an earlier stale draft of the
    Phase 1 reference doc:
        output, session_id, tokens, total_tokens, errors, posts,
        topic, platform, content_intent

    Note: main.py::run() also accepts a `verbose` param that controls
    whether agent logs print to console. This function does not print
    anything by design (the graph is a library-style entry point, not a
    CLI); state["logs"] is still fully populated and available on request
    if a caller wants it — verbosity is a presentation concern, not part
    of this function's return contract, so it's intentionally omitted
    here rather than guessed at.
    """
    from config import SUPPORTED_PLATFORMS

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