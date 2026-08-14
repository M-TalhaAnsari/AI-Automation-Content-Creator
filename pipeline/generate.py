"""
pipeline/generate.py — Core generation pipeline entry point

Split out of main.py per FLOW.md's migration plan ("main.py -> split
into pipeline/generate.py (thin wrapper around workflow/graph.py::
run_graph) + orchestration/dispatch.py (the 8 _handle_* functions) +
slim main.py (CLI entrypoint only)").

STATUS: structural relocation only, run()'s body is UNCHANGED from
main.py -- same fetch/retry/generate/retry logic, same print()-based
progress output, same return shape. This is deliberate: FLOW.md's
stated target is for this function to become a thin wrapper around
workflow/graph.py::run_graph() (which already encodes this same
retry-until-satisfied logic as LangGraph conditional edges, per
agents/00_graph_wiring.md), but that rewiring needs workflow/graph.py's
actual current source to do safely -- guessing at run_graph()'s input/
output state shape here would risk silently breaking behavior instead
of fixing it. Until that file is available, run() keeps its own
fetch/generate retry loop exactly as before, just relocated so
orchestration/dispatch.py and (eventually) the RQ worker can import it
without pulling in any CLI-only code (main.py's interactive_mode,
argparse, print_banner) -- see CLAUDE.md rule 5, "CLI code and worker
code never share a file."

Every internal import below is deliberately deferred (inside the
function body, not at module level) -- this matches the convention
already established throughout main.py's original code and avoids
forcing every caller of this module to eagerly import the whole
understanding/research/generation/workflow/memory stack just to get a
reference to `run`.
"""

import uuid

from Config.config import CONFIG, SUPPORTED_PLATFORMS
from core.state import create_initial_state, get_total_tokens, add_log, add_tokens


def run(prompt: str, platform: str = None, post_count: int = 5, verbose: bool = False) -> dict:
    session_id = str(uuid.uuid4())[:8]
    state = create_initial_state(raw_prompt=prompt, session_id=session_id)
    if platform and platform in SUPPORTED_PLATFORMS:
        state["platform"] = platform
    if post_count:
        state["post_count"] = post_count

    print(f"\n  ┌─ Session: {session_id}")
    print(f"  │  Prompt:  \"{prompt[:72]}{'...' if len(prompt)>72 else ''}\"")
    print(f"  └─ Platform: {state['platform']} | Posts: {state['post_count']}\n")

    print("  [1/5] 🧠 Understanding prompt...")
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
        print(f"        ✅ topic='{state['core_topic']}' | platform={state['platform']} | "
              f"category={state['detected_category']} | tokens={state['tokens']['prompt_parsing']}")
    except Exception as e:
        print(f"        ⚠️  Parser error: {e} — using raw prompt")
        state["core_topic"] = prompt[:60]

    print("  [2/5] 🔀 Selecting sources...")
    try:
        from research.routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
        print(f"        ✅ sources={state['selected_sources']} | method={state['routing_method']}")
    except Exception as e:
        print(f"        ⚠️  Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]

    # ── STEP 3: DATA FETCHERS + QUALITY GATE ─────────────────
    print("  [3/5] 🌐 Fetching live data...")
    try:
        from research.fetchers.fetcher_orchestrator import FetcherOrchestrator
        from workflow.gates import evaluate_fetch_quality, MAX_FETCH_RETRIES

        fetcher = FetcherOrchestrator()
        state = fetcher.fetch(state)
        quality = evaluate_fetch_quality(state)
        print(f"        ✅ {state['total_items_fetched']} items from {state['sources_used']} — {quality['reason']}")

        while not quality["sufficient"] and quality["should_retry"]:
            state["fetch_retry_count"] = state.get("fetch_retry_count", 0) + 1
            next_query = quality.get("next_query")
            print(f"        🔁 Retry {state['fetch_retry_count']}/{MAX_FETCH_RETRIES}: {quality['reason']}")

            if next_query:
                state["fetch_summary"] = next_query
                queries = state.get("search_queries", [])
                state["search_queries"] = [next_query] + [q for q in queries if q != next_query]

            prev_fetched = state.get("fetched_data", {})
            prev_sources = set(state.get("sources_used", []))

            state = fetcher.fetch(state)

            merged = dict(prev_fetched)
            for src, items in state.get("fetched_data", {}).items():
                merged[src] = merged.get(src, []) + items
            state["fetched_data"] = merged
            state["sources_used"] = list(prev_sources | set(state.get("sources_used", [])))
            state["total_items_fetched"] = sum(len(v) for v in merged.values())

            quality = evaluate_fetch_quality(state)
            print(f"        ✅ {state['total_items_fetched']} items from {state['sources_used']} — {quality['reason']}")

        if not quality["sufficient"]:
            state["data_starved"] = True
            print(f"        ⚠️  Data-starved after {state['fetch_retry_count']} retries — "
                  f"proceeding with honest concept-pitch framing instead of fake repo links")

    except Exception as e:
        state["fetched_data"], state["total_items_fetched"], state["sources_used"] = {}, 0, []
        print(f"        ⚠️  Fetch error: {e} — continuing without live data")

    try:
        from memory.session_store import get_already_covered
        state["already_covered"] = get_already_covered(state["core_topic"], state["platform"])
    except Exception as e:
        state["already_covered"] = []
        add_log(state, f"[Main] Already-covered lookup skipped: {e}")

    # ── STEP 4: CONTENT GENERATOR + VALIDATION GATE ──────────
    print("  [4/5] ✨ Generating content...")
    try:
        from generation.content_generator import ContentGenerator
        from workflow.gates import evaluate_post_validation, evaluate_item_kind_match, MAX_GENERATION_RETRIES

        def _validate(state):
            v1 = evaluate_post_validation(state)
            v2 = evaluate_item_kind_match(state)
            return {
                "valid": v1["valid"] and v2["valid"],
                "errors": v1["errors"] + v2["errors"],
                "should_retry": v1["should_retry"] or v2["should_retry"],
            }

        generator = ContentGenerator()
        state = generator.generate(state)
        validation = _validate(state)
        print(f"        ✅ {len(state['generated_posts'])} posts | tokens={state['tokens']['content_generation']}")

        while not validation["valid"] and validation["should_retry"]:
            state["generation_retry_count"] = state.get("generation_retry_count", 0) + 1
            state["generation_validation_errors"] = validation["errors"]
            print(f"        🔁 Retry {state['generation_retry_count']}/{MAX_GENERATION_RETRIES}: "
                  f"{len(validation['errors'])} validation issue(s)")
            for err in validation["errors"][:5]:
                print(f"           - {err}")

            state = generator.generate(state)
            validation = _validate(state)
            print(f"        ✅ {len(state['generated_posts'])} posts | tokens={state['tokens']['content_generation']}")

        if not validation["valid"]:
            print(f"        ⚠️  Still has validation issues after {state['generation_retry_count']} "
                  f"retries — proceeding with best available output")

    except Exception as e:
        print(f"        ❌ Generation failed: {e}")
        state["generated_posts"] = []

    print("  [5/5] 📦 Formatting output...\n")
    from generation.formatter import format_output, save_output
    state = format_output(state)
    saved_path = save_output(state)

    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        add_log(state, f"[Main] Session history save failed: {e}")

    print(state["final_output"])
    if saved_path:
        print(f"\n  💾 Saved to: {saved_path}")
    if verbose and state.get("logs"):
        print("\n  📋 LOGS:")
        for log in state["logs"]:
            print(f"     {log}")
    if state["errors"]:
        print("\n  ⚠️  Warnings:")
        for e in state["errors"]:
            print(f"     • {e}")

    return {
        "output": state["final_output"], "session_id": session_id,
        "tokens": state["tokens"], "total_tokens": get_total_tokens(state),
        "errors": state["errors"], "posts": state["generated_posts"],
        "topic": state.get("core_topic", ""), "platform": state.get("platform", ""),
        "content_intent": state.get("content_intent", ""),
    }