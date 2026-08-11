# Agent 4 — FetchQualityGate

**Core question this agent answers:**
*"Is the data we just fetched actually usable, or do we need to try
again with a different query before spending a generation call on it?"*

- **Type:** Code only. No LLM call. Purely structural checks against
  ground-truth data already in hand.
- **LangGraph node:** Yes — `evaluate_fetch`, conditional edge back to
  `route` (retry) or forward to `generate` (proceed).
- **File:** `workflow/gates.py::evaluate_fetch_quality` — **unchanged**,
  this function is already correctly designed. This file documents its
  contract, not a rewrite.

## Inputs
- `total_items_fetched: int`
- `sources_used: list[str]`
- `fetched_data: dict` (post-reducer-merge — see `00_graph_wiring.md`)
- `content_intent` (from Agent 2)
- `fetch_retry_count: int`

## Output schema
```
{
  "sufficient": bool,
  "reason": str,
  "should_retry": bool,
  "next_query": str | None
}
```

## Checks (all deterministic, no judgment calls)
1. Item count >= `MIN_ITEMS_FLOOR` (3) AND at least one source actually
   returned data.
2. If `content_intent` requires links (`showcase`/`news`/`review`): not
   every fetched link is a generic search-results URL.
3. Retry cap: `MAX_FETCH_RETRIES` (2).

## Must NOT do
- Must never call an LLM to judge "is this data good enough" — that
  question has a deterministic answer (count + source diversity + link
  pattern). If a new failure mode shows up that genuinely requires
  semantic judgment ("this data is topically off"), that belongs in a
  *new*, separately-named agent — do not smuggle a judgment call into
  this gate's code path.
- Must never mutate `fetched_data` itself (e.g. don't dedupe or filter
  items here) — this gate only reads and reports. Merging on retry is the
  state reducer's job (see `00_graph_wiring.md`), not this function's.

## Downstream consumer
`node_evaluate_fetch` (LangGraph node) applies `should_retry` to route the
conditional edge and sets `data_starved=True` when retries are exhausted,
which `GenerationAgent` and `PostValidationGate` both read to relax the
link-required check.
