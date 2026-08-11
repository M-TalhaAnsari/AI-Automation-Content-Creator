# Agent 1 — PromptCleanerAgent

**Core question this agent answers:**
*"What platform, post count, and special requests were stated explicitly
and unambiguously in the raw text, using patterns reliable enough that a
regex can be trusted?"*

- **Type:** Code only. No LLM call. Zero tokens.
- **LangGraph node:** Yes — `prompt_clean`, first node after `START`.
- **Triggered by:** Every fresh generation request (`run_new_request`,
  `generate_more`).
- **File:** `understanding/prompt_cleaner.py` (unchanged location).

## Inputs
- `raw_prompt: str`

## Output schema
```
{
  "detected_platform": str | None,        # only if unambiguous keyword match
  "detected_post_count": int | None,       # only if a bare number is present
  "detected_special_requests": list[str],
  "cleaned_text": str,
  "is_long": bool
}
```

## Must NOT do
- Must not attempt topic extraction — that is `IntentAgent`'s job entirely.
  Do not add a "best-guess topic" field here; `IntentAgent` reads
  `cleaned_text`, not a pre-guessed topic.
- Must not use fuzzy/semantic matching for platform or count. If a value
  isn't a clean, high-confidence pattern match, leave it `None`/empty and
  let `IntentAgent`'s own (schema-validated) judgment fill the gap instead
  of guessing twice.

## Downstream consumer
`IntentAgent` reads `cleaned_text` and the `detected_*` fields as
"already known" context (see Agent 2). `_merge_into_state` in the
orchestration layer uses `detected_post_count` as the **higher-trust**
signal for `post_count_explicit` — see Agent 2's note on this.
