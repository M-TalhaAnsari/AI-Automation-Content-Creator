from typing import TypedDict, List, Dict


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

    fetched_data: Dict[str, List[Dict]]
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