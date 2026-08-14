# CLAUDE.md — TrendForge Session Handoff

> Paste this whole file into a new session (this Claude or any other AI
> assistant) as the first message. It tells you what exists, what's
> done, what's blocked, and what to ask for before touching anything.

## What this is

TrendForge is a multi-agent AI pipeline that turns a raw user prompt
("top 5 ML projects for instagram with github links") into finished
social media posts — understand intent → route to sources → fetch real
data → generate posts → validate → format. LangGraph drives the
fetch/generate retry loop; everything else is direct dispatch.

## Reading order for a new session

1. **This file** — status, rules, what to ask for.
2. **`FLOW.md`** — the pipeline graph, node by node, build status per node.
3. **`ARCHITECTURE.md`** — canonical per-file lookup table. Its own §0
   tells you how to use it ("find your file, do what its entry says").
   **Read that §0 before touching any file.**
4. **`PERFORMANCE_AND_RESILIENCE.md`** — concurrency plan + the
   "how to add error handling without unbounded function growth"
   framework.
5. **`agents/0N_*.md`** — exact prompts/schemas for whichever file
   you're about to touch. Not all exist yet (see ledger below).

## Non-negotiable rules

From `ARCHITECTURE.md` §1, unchanged:
1. One decision, one owner.
2. Structural checks are code; semantic checks are prompts.
3. All LLM calls go through `llm/client.py`. No other file imports
   `groq` or `google.genai`.
4. Structured output only.
5. CLI code and worker code never share a file.

**Added this session:**
6. Schemas in `llm/schemas.py` are **Pydantic models**, not raw
   JSON-schema dicts. `llm/client.py` generates the provider schema via
   `model_json_schema()` but **always** locally re-validates via
   `model_validate_json()` — never trust provider-side enforcement
   alone. Full rationale in `llm/client.py`'s module docstring.
7. `LLMResult.content` stays a plain **dict** (`model.model_dump()`) at
   the boundary, never the Pydantic instance. Every `ARCHITECTURE.md`
   §3 call site expects dict-style `.get(...)`. Don't "upgrade" this
   without also touching every one of those call sites.
8. Every new/rewritten file gets sanity-tested against a mocked
   client + minimal state stub before being handed over. Written-but-
   unrun code doesn't count as done — see "Testing pattern" below, it's
   what caught both critical findings in this ledger.
9. **If a LangGraph state field gets a reducer (`Annotated[T, fn]`),
   every node that doesn't own that field must return through
   `core.state.state_without_reducer_keys()`, not a raw `return state`.**
   LangGraph re-runs a channel's reducer on every node return that
   includes that key, even unchanged — the existing "mutate state in
   place, return the full dict" convention this codebase uses
   everywhere will silently duplicate a reducer-backed field on every
   node hop otherwise. Confirmed by test, not assumed — see
   `core/state.py::merge_fetched_data`'s docstring. This is now the
   pattern; don't add a new reducer field without also auditing every
   node's return for it.

## Status ledger

### ✅ Done and tested this session
| File | What happened |
|---|---|
| `llm/errors.py` | `LLMCallFailed`, `LLMSchemaViolation` — new |
| `llm/schemas.py` | `IntentSchema`, `GeneratedPostsSchema`, `EditSchema`, `ItemKindCheckSchema` — new. No `SelectionSchema` (confirmed dead via `agents/10`) |
| `llm/client.py` | `call_groq`, `call_gemini`, retry policy, local validation — new |
| `understanding/intent_extractor.py` | Rewritten per `agents/02` — gateway-only, no hand-parsed JSON, `platform` dropped, real system/user prompt split |
| `core/state.py` | `fetched_data` reducer + `state_without_reducer_keys()` safety pattern (see rule 9 above — this file's docstrings explain the actual mechanism, worth reading directly) |
| `workflow/gates.py` | `evaluate_item_kind_match` now via `call_groq(schema=ItemKindCheckSchema)`. `evaluate_fetch_quality`/`evaluate_post_validation` untouched — but see 🔴 finding below |
| `workflow/nodes.py` | `node_evaluate_generation` now combines both validation gates (was the "one live bug"). Every node updated for the reducer-safety pattern |
| `workflow/graph.py` | Redundant timeout wrapper removed — see 🔴 finding below |

### ✅ Confirmed correct, no action needed
`understanding/prompt_cleaner.py` (cross-checked against `agents/01`).

### 🔴 Two findings from this session, unresolved — read before continuing
1. **`evaluate_fetch_quality` (`workflow/gates.py`) likely has a real bug**, exposed (not caused) by the `fetched_data` reducer. Proven with a live end-to-end run, not a guess: `fetched_data` correctly accumulated to 6 real items across 3 fetch attempts, but `total_items_fetched` stayed at 2 (whatever the last attempt reported) because it has no reducer — so the retry loop burned both retries and set `data_starved=True` despite having enough real data by attempt 2. Not fixed — `ARCHITECTURE.md` says this function needs nothing, and I don't have `fetcher_orchestrator.py` to confirm the count is really per-attempt rather than already-running-total. If confirmed, the fix is one line: derive the count from `fetched_data` directly instead of the separate field. **Get `fetcher_orchestrator.py` to settle this.**
2. **CLI timeout gap.** Deleting `workflow/graph.py`'s timeout wrapper (per spec) assumed `run_graph()` is only ever reached via the RQ worker (`job_timeout=180`). It's also reached from `main.py`'s CLI path with no RQ involved at all — so CLI usage now has zero timeout protection where it used to have a 90s backstop as its only one. Decide deliberately: either `main.py`'s CLI path needs its own wrapper, or this is an accepted gap.

### 🔴 Still highest priority, not started (safety, not just cleanup)
`conversation/orchestrator.py` → `orchestration/conversation_agent.py`
(needs `agents/08_conversation_agent.md`, **not yet sent**). Two return
paths in `process_turn` can resolve to `run_new_request` without the
destructive-action confirmation gate. `ARCHITECTURE.md` calls this out
by name as a live bug, not a maintainability item.

### ⬜ Spec in hand, current source still needed
| File | Spec doc I have | Source needed |
|---|---|---|
| `generation/content_generator.py` | `agents/05_generation_agent.md` | not sent |
| `generation/formatter.py` | none — `ARCHITECTURE.md` §6, unaudited | not sent (also answers content_generator.py fix #5) |
| `conversation/actions.py` | fix fully specified inline in `ARCHITECTURE.md`, uses `EditSchema` (built) | not sent |
| `research/fetchers/fetcher_orchestrator.py` | described in `ARCHITECTURE.md`, not a dedicated agent doc | not sent — **now also needed to resolve finding #1 above** |

### ⬜ Neither spec nor source in hand
`research/routing/llm_router.py`, `api/web/handlers.py`, `main.py` (the
three-way split), `config/*`, everything in `ARCHITECTURE.md` §6.

### Open decisions flagged, not resolved
- `post_count`: `IntentSchema` caps at 10; `intent_extractor.py`'s own
  clamp still says 20. Both ship as-is, disagreeing.
- `CONFIG.models.gemini_api_key` — guessed by analogy with the
  confirmed `groq_api_key`. Unverified; `config/` is unaudited.
- Hashtag schema pattern (`^#`) turns a previously-silent code fix into
  a hard `LLMSchemaViolation` on that call. Intentional per spec, just
  worth knowing operationally.

## Testing pattern established this session

Stub `core/state.py` + `Config/config.py` minimally, monkeypatch
`call_groq`/`call_gemini` (or, for graph-level work, stub the actual
pipeline modules with deliberately adversarial behavior — undershoot
the item floor, produce an invalid post — to force the retry paths to
actually fire), then run the real function/graph and check the result.
Both critical findings in this ledger came directly from doing this,
not from reading the code. Keep doing it for every remaining file.

## Recommended next action

Get `agents/08_conversation_agent.md` + current `conversation/
orchestrator.py` — it's the one live safety bug on this whole list.
`fetcher_orchestrator.py` is the next most valuable ask after that,
since it resolves an open bug rather than just unblocking a pending fix.