# FLOW.md — TrendForge Pipeline, Node by Node

Canonical graph design: `agents/00_graph_wiring.md`. This file is the
same graph with build status attached per node — if this ever seems to
disagree with `agents/00` on the design itself (not the status), that
file wins.

## Which actions use the graph

| Action | Uses graph? | Why |
|---|---|---|
| `run_new_request` | **Yes** | fetch→generate, needs both quality gates and retry |
| `generate_more` | **Yes** | same shape, appended rather than replacing |
| `edit_existing` | No | single LLM rewrite, no fetch, no retry loop |
| `targeted_refetch` | No | one fetch + one generate, no retry loop today |
| `undo` | No | pure state manipulation |
| `add_constraint` / `remove_constraint` | No | pure state manipulation |
| `clarify` | No | terminal |

## The graph

```
START
  │
  ▼
[parse]                 code + LLM (bundles prompt_clean + intent)
  │                      understanding/prompt_parser.py
  │                      ✅ prompt_cleaner.py confirmed OK (agents/01)
  │                      ✅ intent_extractor.py rewritten this session (agents/02)
  │                      ⚠️  agents/00's diagram shows prompt_clean and
  │                          intent as two SEPARATE nodes (to eventually
  │                          run route concurrently with intent — see
  │                          PERFORMANCE_AND_RESILIENCE.md §1.2). This
  │                          codebase still bundles them into one "parse"
  │                          node via PromptParser. Not split in this
  │                          session — §1.2 marks it "optional, conditional
  │                          payoff," not a correctness fix, and splitting
  │                          it means restructuring node_parse + the graph
  │                          edges, a bigger, separately-scoped change.
  ▼
[route]                 code + LLM fallback
  │                      research/routing/{rule_router,llm_router}.py
  │                      ⬜ rule_router.py: OK, no change (ARCHITECTURE.md §5)
  │                      ⬜ llm_router.py: needs 1-line fix (add "github"
  │                          to fallback list) — source not sent yet
  ▼
[fetch]                 code, retry target
  │                      research/fetchers/fetcher_orchestrator.py
  │                      ⬜ NOT SENT. Structurally OK per ARCHITECTURE.md,
  │                          parallel fan-out is an optional enhancement.
  │                          🔴 Also now needed to resolve the
  │                          total_items_fetched bug — see CLAUDE.md
  │                          finding #1.
  ▼
[evaluate_fetch]        code — workflow/gates.py::evaluate_fetch_quality
  │                      ✅ untouched, per spec ("needs nothing")
  │                      🔴 but see CLAUDE.md finding #1 — untouched
  │                          doesn't mean confirmed-correct anymore
  ├─ sufficient ──────► generate
  └─ insufficient,
     retries left ─┐
                    │  loops back to route. fetched_data ACCUMULATES via
                    │  reducer now — ✅ core/state.py, tested this session
                    │  (proven correct even under duplicate-source-key
                    │  accumulation across 3 real retry attempts)
                    └─────────────────────────────────────────┘
  ▼
[generate]              LLM (Gemini→Groq fallback)
  │                      generation/content_generator.py + prompt_composer.py
  │                      ⬜ NOT STARTED — largest remaining fix (agents/05,
  │                          have spec, need source). prompt_composer.py
  │                          itself needs no change per ARCHITECTURE.md.
  ▼
[evaluate_generation]   code + LLM, ONE combined node
  │                      workflow/gates.py (post_validation + item_kind_match)
  │                      workflow/nodes.py::node_evaluate_generation
  │                      ✅ DONE this session — this was the one live bug:
  │                          ItemKindGate was built but never reachable
  │                          from the graph before this fix (agents/06 +
  │                          agents/07)
  ├─ valid ───────────► format
  └─ invalid,
     retries left ─────► generate
  ▼
[format] → END          generation/formatter.py
                         ⬜ NOT SENT (ARCHITECTURE.md §6, unaudited).
                         Also needed to answer content_generator.py fix #5
                         (is content_generation_engine=="None" surfaced
                         to the user anywhere?)
```

## Non-graph dispatch (`orchestration/dispatch.py`)

| Action | Handler | Status |
|---|---|---|
| `edit_existing` | `conversation/actions.py::_edit_via_gemini`/`_edit_via_groq` | ⬜ NOT STARTED. Fix uses `EditSchema` (already built in `llm/schemas.py`) — just needs `conversation/actions.py` source |
| `targeted_refetch` | `conversation/actions.py::targeted_refetch` | ⬜ NOT STARTED. Known bug: hardcodes `content_intent="showcase"`, needs a parameter instead |
| `undo` / `add_constraint` / `remove_constraint` | — | ⬜ NOT YET AUDITED (§6) |
| `clarify` | — | ⬜ NOT YET AUDITED (§6) |
| all of the above | `orchestration/conversation_agent.py` decides which action a chat turn maps to | 🔴 **NOT STARTED — the one live safety bug.** Needs `agents/08_conversation_agent.md` (not sent) + current `conversation/orchestrator.py` source |

## Structural work still pending (not part of the graph itself)

- `main.py` → split into `pipeline/generate.py` (thin wrapper around
  `workflow/graph.py::run_graph`) + `orchestration/dispatch.py` (the 8
  `_handle_*` functions) + slim `main.py` (CLI entrypoint only). Not
  started — needs `main.py` source.
- `web/redis_store.py` → **DELETE**. Confirmed broken (can't run as
  written) and missing `pending_confirmation` entirely. Search the repo
  for any import of `web.redis_store` before deleting — if referenced,
  repoint that call site at `memory/redis_session_store.py` first.
- `api/web/handlers.py` → one-line import fix (`import main` →
  `import orchestration.dispatch as dispatch`). Not started, source not sent.