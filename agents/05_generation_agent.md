# Agent 5 — GenerationAgent (updated — now owns selection too, see revision note)

> **Revision note:** an earlier pass formalized item-selection as a
> separate Agent 10 (`SelectionAgent`). That was reconsidered once the
> question became "minimize LLM round trips" — `prompt_composer.py`
> already shows this call comparable data coverage to what a separate
> selection pass would see, so splitting them was two calls doing
> overlapping work. Selection is now folded into this agent. See
> `agents/10_selection_agent.md` for the full reasoning behind the merge.

**Core question this agent answers:**
*"Given the real fetched data and the user's intent, which items are
worth using, and what should each resulting post actually say?"*

- **Type:** LLM (Gemini primary, Groq large as fallback), structured
  output.
- **LangGraph node:** `generate`, also the retry target when
  `evaluate_generation` fails and retries remain.
- **File:** `generation/content_generator.py` (entry point) +
  `generation/prompt_composer.py` (prompt assembly).
- **Calls through:** `llm/client.py::call_gemini(schema=GeneratedPostsSchema)`,
  falling back to `call_groq(...)` on Gemini failure.

## Inputs
- `core_topic`, `content_intent`, `item_kind`, `raw_prompt` (Agent 2)
- `platform`, `post_count`, `post_count_explicit` (Agent 1 + Agent 2)
- `fetched_data` — **the full quality-gate-passed set, not a
  pre-selected subset.** `content_generator.py` no longer regroups to a
  selected subset before calling `compose_prompt()`; `prompt_composer.py`
  shows more candidates per source than the target post count so the
  model has genuine choice.
- `already_covered` (memory/session_store — avoid repeat titles)
- `generation_retry_count`, `generation_validation_errors` (if this is a
  retry pass)

## Output schema — `GeneratedPostsSchema`
```
{
  "posts": [
    {
      "number": int,
      "title": str, "hook": str,
      "summary": list[str],
      "link": str,
      "caption": str,
      "hashtags": list[str]   # schema pattern "^#" — no code-level
                                #   normalization loop needed anymore
    }, ...
  ],
  "series_hook": str,
  "trend_insight": str
}
```
No separate `selected_indices` field — selection and writing happen in
one pass, one output.

## Prompt change from the merge
Add one line to `prompt_composer.py`'s core instructions block:
*"You may be shown more candidate items than needed — select the
{post_count} most engaging and relevant for {platform} before writing.
Ignore the rest."* No schema change required beyond the hashtag pattern
constraint above.

## Design that's already correct — do not change
- Two independent strategy axes (Intent vs Platform), combined only in
  `prompt_composer.py`.
- Correction block on retry — fixing structural errors with the exact
  prior error text is the right use of a retry.

## Hard constraint (code-enforced, not prompt-requested)
`PostValidationGate` strips any `link` that doesn't exactly match a URL
present in `fetched_data`, unconditionally — do not rely on the prompt's
"don't invent links" instruction alone.

## ItemKindGate — conditional invocation (optional optimization)
Default: always run `ItemKindGate` after this call when `item_kind` is
non-empty. **Optional, stakes-based relaxation:** for `generate_more`
specifically (lower stakes than a first `run_new_request`), skip
`ItemKindGate` on the first attempt and only invoke it if
`PostValidationGate` already triggered a retry for an unrelated
structural reason — i.e., pay for the extra semantic check exactly when
something's already looking shaky, not on every call. This is a genuine
quality/speed tradeoff, not a default — decide per your own risk
tolerance, not something to apply silently.

## Must NOT do
- Must not be asked to also self-judge item_kind correctness as part of
  its own output ("and double-check each title matches") — self-critique
  in the same context as authorship is unreliable. `ItemKindGate` stays
  a separate, fresh-context call specifically because of this.

## Downstream consumer
`PostValidationGate` and (conditionally) `ItemKindGate` read
`generated_posts`. `formatter.py` reads the final validated set.
