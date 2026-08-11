# Agent 10 — SelectionAgent — MERGED into Agent 5, kept here for traceability

> **Status: deprecated as a standalone agent.** This file originally
> formalized item-selection ("pick the best N of the fetched items") as
> its own LLM call, separate from `GenerationAgent`. Revisiting that
> decision specifically under a minimize-round-trips lens: it was the
> wrong split. Kept here, rewritten, rather than deleted outright — so
> anyone (human or AI assistant) who lands on this file understands
> *why* the merge happened instead of finding a silently vanished file
> and wondering if something was missed.

## Why this was split out in the first place
`content_generator.py::_select_best_items` existed as its own LLM call,
own schema, own Gemini→Groq fallback, run before the main generation
call, to narrow >20 fetched items down to the target `post_count`
before writing.

## Why it's wrong as a separate call
`prompt_composer.py`'s `data_block` already shows the generation call
comparable coverage of the same fetched data (items per source across
every source used). The two calls were both reading essentially the
same material to make two different but overlapping judgments — "is
this item good" and "what should I write about this item" — which is
exactly the kind of over-decomposition this whole redesign has been
removing elsewhere (see the original audit's root-cause section on
decisions split across mechanisms with no single owner). The fix here
isn't ownership conflict (both calls agreed on quality most of the
time) — it's **redundant work**: paying for a full LLM round trip to
answer a question the very next call was already positioned to answer
as a side effect of the work it does anyway.

## What replaced it
See `agents/05_generation_agent.md`. Concretely:
- `content_generator.py` no longer regroups `fetched_data` to a
  pre-selected subset before calling `compose_prompt()`.
- `prompt_composer.py` shows a slightly higher item-per-source cap so
  the model has genuine choice.
- One line was added to the generation prompt's core instructions
  asking the model to select the best `{post_count}` from what it's
  shown before writing.
- No new schema needed — `GeneratedPostsSchema` already only asks for
  the final `post_count` posts; there's no `selected_indices` field to
  design or maintain.

## If you're tempted to re-split this in the future
Re-split it only if you find a concrete reason the merged version is
producing worse selections than the old two-pass version did in
practice (e.g. a regression-set case where the model picks poor items
when also asked to write about them, but picked well when selection was
its only job that turn). Don't re-split on a hunch that "more focused
calls are more reliable" without that evidence — that reasoning is what
justified the original split, and it turned out to cost a full round
trip for no measurable benefit.
