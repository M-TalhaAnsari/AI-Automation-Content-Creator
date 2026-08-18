# CLAUDE.md — TrendForge Session Handoff (Session 4)

> Paste this whole file into a new session as the first message.
>
> **This is the fourth handoff.** It updates the codebase status following the direct audit and empirical verification of real repository sources (including `workflow/gates.py`, `research/fetchers/fetcher_orchestrator.py`, `conversation/actions.py`, `workflow/graph.py`, and `llm/errors.py`).

## What this is

TrendForge is a multi-agent AI pipeline that turns a raw user prompt into finished social media posts — understand intent → route to sources → fetch real data → generate posts → validate → format.
LangGraph drives the fetch/generate retry loop; conversational actions (`generate_more`, `edit_existing`, `targeted_refetch`, etc.) are direct dispatch, outside the graph.

## Reading order for a new session

1. **This file** — status, rules, what to ask for.
2. **`workflow/flow.md`** — the pipeline graph, node by node, build status.
3. **`architecture.md`** / **`agents/ARCHITECTURE.md`** — canonical lookup tables and agent specs.

## Non-negotiable rules

1. One decision, one owner.
2. Structural checks are code; semantic checks are prompts.
3. All LLM calls go through `llm/client.py`. (Exceptions: `orchestration/conversation_agent.py` and `research/routing/llm_router.py` tool-calling / low-level routing).
4. Structured output only via Pydantic schemas in `llm/schemas.py`.
5. CLI code and worker code never share a file.
6. Schemas in `llm/schemas.py` are Pydantic models; `llm/client.py` always locally re-validates via `model_validate_json()`.
7. `LLMResult.content` stays a plain dict at the boundary.
8. Every new/rewritten file gets sanity-tested directly.
9. Reducer-owned state fields (`fetched_data`) must be excluded from any node's return value unless that node owns the field — see `core/state.py::state_without_reducer_keys()`.

---

## Status Ledger & Verified Fixes

### ✅ Confirmed & Empirically Verified in Real Source (Session 4)

| Item | File(s) | How it was verified |
|---|---|---|
| **Bug 1: Item-kind check silent failure & token starvation** | `workflow/gates.py::evaluate_item_kind_match` | Fixed missing `max_tokens=300` alongside `reasoning_effort="low"`. Replaced bare silent `except Exception: return {"valid": True}` with `logger.warning(...)` so failures are logged rather than silently passing off-topic content. |
| **Bug 2: Asymmetric token tracking in edits** | `conversation/actions.py::edit_existing` | Added `tokens_used += getattr(e, "tokens_used", 0)` to the Gemini exception catch block, matching the Groq block. |
| **Bug 4: Non-accumulating fetch stats across retries** | `research/fetchers/fetcher_orchestrator.py` | `total_items_fetched` now accumulates (`+= total_items`) across retries; `sources_used` deduplicates while preserving order using `dict.fromkeys`. |
| **Bug 5: Missing `search_queries` in targeted refetch gate dict** | `conversation/actions.py::targeted_refetch` | Computed `combined_topic` early and passed `search_queries: [combined_topic]` into `fake_state_for_gate` so `evaluate_fetch_quality` can return a valid `next_query`. |
| **Graph Compilation & Architecture Check** | `workflow/graph.py`, `core/state.py` | Compiled LangGraph `StateGraph` successfully with all 8 nodes (`parse`, `route`, `fetch`, `evaluate_fetch`, `generate`, `evaluate_generation`, `format`) and initialized 35-key `TrendForgeState`. |

---

## Prior False Positives Resolved

- **`KeyError: 'logs'` finding in `fetcher_orchestrator.py`**: The real file uses standard Python `logging` and `state.setdefault("errors", []).append(...)` rather than `add_log()`. The `create_initial_state()` usage in `dispatch.py` and `actions.py` is kept as safe defensive coding.
- **Alleged `.values()` unpacking crash in `gates.py`**: Real file line 32 was already using `fetched_data.items()`.
- **`LLMCallFailed` signature**: Constructed cleanly with single positional messages in `llm/client.py`.