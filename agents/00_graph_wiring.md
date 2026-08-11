# TrendForge — LangGraph Wiring (Corrected)

> Supersedes §5 of `TrendForge_Architecture_Redesign.md`. That section said
> "delete `workflow/graph.py`." This document reverses that, narrowly: the
> looping requirement (retry fetch/generation until a quality gate is
> satisfied) is exactly what LangGraph's conditional edges are built for.
> The procedural version in `main.py` was only ever a stand-in for this.

## Scope: which actions use the graph

Only actions with genuine "try, check quality, retry" semantics use the
graph. Everything else stays a direct function call.

| Action | Uses graph? | Why |
|---|---|---|
| `run_new_request` | **Yes** | fetch→generate, needs both quality gates and retry |
| `generate_more` | **Yes** | same fetch→generate shape, appended rather than replacing |
| `edit_existing` | No | single LLM rewrite call, no fetch, no quality-gate retry |
| `targeted_refetch` | No | one fetch + one generate, no retry loop today (could be added later if it earns one) |
| `undo` | No | pure state manipulation, no LLM call at all |
| `add_constraint` / `remove_constraint` | No | pure state manipulation |
| `clarify` | No | terminal — nothing to execute |

## Corrected graph

```
START
  │
  ▼
prompt_clean          (code — PromptCleanerAgent)
  │
  ▼
intent                (LLM — IntentAgent)
  │
  ▼
route                 (code/LLM-fallback — RouterAgent)
  │
  ▼
fetch  ────────────────────────────┐
  │                                │
  ▼                                │
evaluate_fetch        (code — FetchQualityGate)
  │                                │
  ├─ sufficient ──► generate       │
  └─ insufficient, retries left ───┘  (loops back to route; fetched_data
                                       ACCUMULATES via state reducer —
                                       see below, not manual dict merging)
  │
  ▼
generate               (LLM — GenerationAgent)
  │
  ▼
evaluate_generation     (code + LLM — PostValidationGate + ItemKindGate,
  │                      ONE node, both gates, combined result —
  │                      this is the fix: graph.py previously only
  │                      called PostValidationGate here)
  ├─ valid ──────────► format
  └─ invalid, retries left ──► back to generate
  │
  ▼
format → END
```

## Fix 1 — `evaluate_generation` calls both gates

```
node_evaluate_generation(state):
    v1 = evaluate_post_validation(state)      # workflow/gates.py, unchanged
    v2 = evaluate_item_kind_match(state)      # workflow/gates.py, unchanged,
                                               #   now via llm/client.py
    combined_valid = v1["valid"] and v2["valid"]
    combined_errors = v1["errors"] + v2["errors"]
    should_retry = (v1["should_retry"] or v2["should_retry"])
    # exact same combination logic main.py's _validate() already uses —
    # just finally reachable from the graph too.
```

## Fix 2 — accumulation via state reducer, not manual merge

Declare `fetched_data` in `TrendForgeState` (`core/state.py`) with a custom
reducer instead of a plain dict field:

```
def merge_fetched_data(existing: dict, new: dict) -> dict:
    merged = dict(existing)
    for source, items in new.items():
        merged[source] = merged.get(source, []) + items
    return merged

fetched_data: Annotated[dict, merge_fetched_data]
```

Every time the graph loops `evaluate_fetch → route → fetch`, LangGraph
calls this reducer automatically on the node's return value. No node has
to remember to merge — this is what actually eliminates the "second
mechanism nobody remembers is there" risk, rather than porting the manual
merge code from `main.py` verbatim.

## Fix 3 — one timeout

Delete `GRAPH_TIMEOUT_SECONDS` and the `ThreadPoolExecutor` wrapper in
`graph.py`'s `run_graph()`. The graph is invoked from inside
`api/web/jobs.py::run_slow_action`, which already runs inside an RQ job
with `job_timeout=180` (set in `api/web/app.py`'s `_queue.enqueue(...)`
call). One clock, owned by RQ, not two racing each other with different
failure behavior.

## What `pipeline/generate.py` becomes

A thin wrapper, not a procedural reimplementation:

```
pipeline/generate.py
    def run(prompt, platform=None, post_count=5) -> dict:
        state = create_initial_state(...)
        final_state = compiled_graph.invoke(state)
        return { ...same 9-key contract main.py:run() already returns... }
```

`orchestration/dispatch.py`'s `_handle_run_new_request` and
`_handle_generate_more` call this instead of the old procedural loop.
