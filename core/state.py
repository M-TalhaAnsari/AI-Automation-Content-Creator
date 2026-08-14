from typing import Annotated, TypedDict, List, Dict


def merge_fetched_data(existing: dict, new: dict) -> dict:
    """
    FIX (ARCHITECTURE.md workflow/graph.py entry, Fix 2 /
    agents/00_graph_wiring.md): LangGraph reducer for the `fetched_data`
    channel. Without this, every time the graph loops back through
    evaluate_fetch -> route -> fetch on a retry, the fetch node's return
    value overwrote fetched_data outright — attempt 1's results were
    silently discarded the moment attempt 2 ran.

    IMPORTANT — read this before adding any other reducer-backed field:
    LangGraph calls a channel's reducer on EVERY node return that
    includes that key, not just when a node actually changes it, and it
    doesn't matter whether the value is the literal same object — it
    still gets merged again. Every node function in workflow/nodes.py
    follows this codebase's existing convention of mutating `state` in
    place and returning the full dict. Verified by test: with that
    convention unchanged, adding this reducer duplicates fetched_data at
    EVERY node hop after fetch runs, not just at retries — a single
    fetch -> evaluate_fetch -> generate -> evaluate_generation -> format
    pass with zero retries would end up roughly 16x-duplicated by the
    time it reaches formatting, worse than the bug being fixed.

    The fix that makes this safe: REDUCER_OWNED_KEYS and
    state_without_reducer_keys() below. Every node except the one that
    actually owns a reducer-backed field must exclude that field from
    its return value (a partial update omitting the key), not echo back
    the full state. workflow/nodes.py applies this to every node.
    """
    merged = dict(existing)
    for source, items in new.items():
        merged[source] = merged.get(source, []) + items
    return merged


# Keys with a channel reducer registered in TrendForgeState below. If you
# add another Annotated[..., reducer_fn] field, add its key here too —
# see state_without_reducer_keys()'s docstring for why this matters.
REDUCER_OWNED_KEYS = frozenset({"fetched_data"})


def state_without_reducer_keys(state: dict, owns: frozenset = frozenset()) -> dict:
    """
    Every workflow/nodes.py node function should return through this
    (or build its return dict the same way) instead of `return state`
    directly, UNLESS it's the node that actually owns a reducer-backed
    field for that call (pass that field's name in `owns`).

    Returning the full state naively re-submits every reducer-backed
    key's current (already-merged) value on every single node hop,
    which LangGraph then merges AGAIN against itself — silent, steadily
    compounding duplication with no error, no warning, nothing in the
    logs to catch it. See merge_fetched_data's docstring for the test
    that confirmed this.
    """
    exclude = REDUCER_OWNED_KEYS - owns
    return {k: v for k, v in state.items() if k not in exclude}


class TrendForgeState(TypedDict):
    raw_prompt: str
    session_id: str

    core_topic: str
    platform: str
    post_count: int
    content_type: str
    special_requests: List[str]
    detected_category: str
    content_intent: str
    item_kind: str                      # e.g. "a named API or protocol" -- set only when the
                                         # user asked for N discrete named things, not sub-concepts
                                         # of one topic. Empty string means no constraint applies.
    is_long_prompt: bool

    selected_sources: List[str]
    routing_method: str

    # FIX: was `Dict[str, List[Dict]]` (plain field, last-write-wins under
    # LangGraph). Now accumulates across fetch retries via
    # merge_fetched_data above — see that function's docstring for the
    # companion fix (state_without_reducer_keys) this requires elsewhere.
    fetched_data: Annotated[Dict[str, List[Dict]], merge_fetched_data]
    fetch_summary: str
    search_queries: List[str]
    total_items_fetched: int
    trend_insight: str
    already_covered: List[Dict]

    generated_posts: List[Dict]
    final_output: str
    content_generation_engine: str

    tokens: Dict[str, int]

    errors: List[str]
    warnings: List[str]
    logs: List[str]
    sources_used: List[str]

    data_starved: bool
    fetch_retry_count: int
    generation_retry_count: int
    generation_validation_errors: List[str]

    active_constraints: List[Dict]
    leftover_fetch_pool: List[Dict]

    fetch_should_retry: bool
    generation_should_retry: bool


def create_initial_state(raw_prompt: str, session_id: str) -> TrendForgeState:
    return TrendForgeState(
        raw_prompt=raw_prompt,
        session_id=session_id,
        core_topic="",
        platform="instagram",
        post_count=5,
        content_type="posts",
        special_requests=[],
        detected_category="unknown",
        content_intent="",
        item_kind="",
        is_long_prompt=len(raw_prompt) > 120,
        selected_sources=[],
        routing_method="",
        fetched_data={},
        fetch_summary="",
        search_queries=[],
        total_items_fetched=0,
        trend_insight="",
        already_covered=[],
        generated_posts=[],
        final_output="",
        content_generation_engine="",
        tokens={"prompt_parsing": 0, "source_routing": 0, "data_fetching": 0, "content_generation": 0},
        errors=[],
        warnings=[],
        logs=[],
        sources_used=[],
        data_starved=False,
        fetch_retry_count=0,
        generation_retry_count=0,
        generation_validation_errors=[],
        active_constraints=[],
        leftover_fetch_pool=[],
        fetch_should_retry=False,
        generation_should_retry=False,
    )


def add_log(state: TrendForgeState, message: str) -> None:
    state["logs"].append(message)


def add_error(state: TrendForgeState, message: str) -> None:
    state["errors"].append(message)


def add_tokens(state: TrendForgeState, layer: str, count: int) -> None:
    if layer in state["tokens"]:
        state["tokens"][layer] += count
    else:
        state["tokens"][layer] = count


def get_total_tokens(state: TrendForgeState) -> int:
    return sum(state["tokens"].values())