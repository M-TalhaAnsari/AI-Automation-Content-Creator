# Agent 3 — RouterAgent

**Core question this agent answers:**
*"Which data sources are likely to have real information on this topic?"*

- **Type:** Code first (`RuleRouter`, 0 tokens), LLM fallback only when the
  rule table has no confident match (`LLMRouter`, Groq small, ~100t).
- **LangGraph node:** Yes — `route`, runs after `intent`, and again on
  every fetch-quality retry loop-back.
- **File:** `research/routing/router_orchestrator.py` (unchanged design —
  this file already correctly does "deterministic first, LLM fallback
  second," which is the right pattern; nothing to fix here).

## Inputs
- `category` (from Agent 2)
- `detected_category` confidence / presence in `SOURCE_MAP`

## Output schema
```
{
  "selected_sources": list[str],
  "routing_method": "rule" | "llm_fallback"
}
```

## Must NOT do
- The LLM fallback must not re-derive `category` — it only picks sources
  given the category Agent 2 already decided. If category itself seems
  wrong, that is Agent 2's prompt to fix, not a reason to add
  category-guessing logic here.

## Downstream consumer
`FetcherOrchestrator` (research/fetchers/fetcher_orchestrator.py) reads
`selected_sources` directly.
