# Agent 6 — PostValidationGate

**Core question this agent answers:**
*"Is each generated post structurally correct — real fields, real links,
within platform limits, not a duplicate?"*

- **Type:** Code only. No LLM call. Every check is a deterministic fact
  comparison, several against ground-truth data the system already holds.
- **LangGraph node:** Part of the combined `evaluate_generation` node
  (see `00_graph_wiring.md`, Fix 1) — runs alongside Agent 7, not as a
  separate node.
- **File:** `workflow/gates.py::evaluate_post_validation` — **unchanged**,
  already correctly designed.

## Inputs
- `generated_posts` (Agent 5's output)
- `platform` → `PLATFORM_SETTINGS[platform].max_caption_chars`
- `content_intent` → is a link required
- `fetched_data` → the set of real links, for the hallucination check
- `data_starved` (from Agent 4, relaxes link-required check when true)

## Output schema
```
{ "valid": bool, "errors": list[str], "should_retry": bool }
```

## Checks (all deterministic)
1. Required fields present (`title`, `hook`, `caption`) and non-empty.
2. `summary` is a non-empty list. `hashtags` is a non-empty list.
3. If `content_intent` requires a link and not `data_starved`: link is
   present.
4. If a link is present: not a generic search-engine URL, **and** it
   must appear verbatim in the set of real links collected from
   `fetched_data` — this is the hallucination guard. An empty
   `real_links` set (fetch legitimately returned nothing) skips this
   specific check rather than blocking on an unrelated infra gap.
5. Caption length within the platform's limit.
6. No near-duplicate titles within the same batch.

## Must NOT do
- Must never ask "does this title match what the user meant by
  item_kind" — that is a semantic judgment and belongs entirely to
  Agent 7. Do not add fuzzy/semantic checks to this function; if a check
  needs judgment rather than a fact comparison, it is not this agent's
  job.

## Downstream consumer
`node_evaluate_generation` combines this with Agent 7's result to decide
`generation_should_retry`; `prompt_composer.py`'s correction block reads
`errors` on the next attempt.
