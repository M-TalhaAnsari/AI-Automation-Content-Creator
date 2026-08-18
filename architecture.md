# TrendForge — Architecture Reference

> **Updated this session (empirical verification pass).** Previous
> versions of this document were built from source review and reasoning
> about the code. This version's changes were built by reconstructing
> the real project in a sandbox — real `pydantic`, real `langgraph`,
> real `groq`/`google-genai` SDKs, with only the outbound network call
> mocked — and actually running it. Where a fix below is marked
> "verified," that means a test was executed that would have failed
> under the old code and passes under the new code, not just that the
> diff looks correct on inspection. Sections not touched this session
> (env vars, docker compose, frontend, most of `config/`) are carried
> forward unchanged and are not re-verified here.

---

## 1. What TrendForge Does (One Paragraph)

TrendForge takes a user's natural-language content idea, fetches real
live data from multiple sources, selects the best items, generates
platform-ready posts using an LLM, and returns structured post objects.
It has a web API, a Redis-backed session system, and an RQ background
job queue for the slow pipeline steps.

---

## 2. System-Level Data Flow

```
User message (HTTP POST /chat)
        │
        ▼
api/web/app.py          ← JWT auth, rate limiting, session resolution
        │
        ├─ INLINE actions (add_constraint, remove_constraint, clarify)
        │   └── orchestration/conversation_agent.py → conversation/actions.py
        │
        └─ SLOW actions (run_new_request, edit_existing, targeted_refetch, generate_more)
            └── RQ job enqueued → api/web/jobs.py
                    │
                    ▼
            api/web/handlers.py::finalize_turn()
                    │
                    ▼
            orchestration/dispatch.py::dispatch_action()
                    │
          ┌─────────┼───────────────────────────────────────┐
          ▼         ▼                                       ▼
   run_new_request  generate_more / edit_existing /   add_constraint /
   (via pipeline/    targeted_refetch (direct calls,  remove_constraint /
   generate.py::run  now gate-enforced via             undo / clarify
   → workflow/graph   _generate_with_validation --       (pure conversation-
   .py::run_graph)    see §3 "Known gap, CLOSED")        dict manipulation)
          │
          ▼
   workflow/graph.py's compiled LangGraph:
   parse → route → fetch ⇄ evaluate_fetch (retry loop)
         → generate ⇄ evaluate_generation (retry loop)
         → format
          │
          ▼
   memory/session_store (permanent JSON history)
          │
          ▼
     reply → frontend
```

**FIX (this session, verified — see §3 `orchestration/` entry):**
`generate_more` and `targeted_refetch` used to call
`ContentGenerator().generate(state)` once with no retry loop and no gate
enforcement — flagged across three prior sessions as "Known gap, not yet
resolved." This session closed it: both now go through
`orchestration/dispatch.py::_generate_with_validation()`, a manual retry
loop calling the same `workflow/gates.py` functions the graph uses.
Verified with a real forced validation failure (duplicate titles on
attempt 1, clean on attempt 2) — confirmed exactly 2 generation calls
were made, not 1, and the retry cap (proceed with best-effort after
`MAX_GENERATION_RETRIES`) was confirmed to not loop forever.

---

## 3. Module Reference

### `core/`
Unchanged this session. `state_without_reducer_keys()`/`REDUCER_OWNED_KEYS`
discipline confirmed correct via real `langgraph` execution across every
test this session (not just re-asserted).

---

### `config/` (real folder name: `Config`, capital C)
**STATUS: still unaudited beyond what was directly needed this session.**
`Config/config.py`'s real source was reviewed and used as-is in the
sandbox; nothing in it was changed. `CONFIG.models.gemini_api_key` and
`PLATFORM_SETTINGS` are confirmed real and correct (used successfully in
every test this session), superseding the "unverified guess" note in
earlier versions of this document.

---

### `llm/` — gateway, now the ONLY path for content-affecting generation

| File | Status this session |
|---|---|
| `client.py` | Real source, unmodified. **Verified, not just reviewed:** `call_gemini`/`call_groq`'s retry-then-fail policy was observed executing for real (3 attempts logged, matching `_MAX_RETRIES=2`, including the actual `time.sleep()` backoff) when both providers were forced to fail in a test. Schema validation via `model_validate_json()` was observed correctly raising `LLMSchemaViolation` on a real malformed hashtag (missing `#`), with the real pydantic error text captured. |
| `schemas.py` | Real source, unmodified. `GeneratedPostsSchema`, `EditSchema`, `ItemKindCheckSchema`, and the `Hashtag` pattern constraint all exercised successfully this session. |
| `errors.py` | **STILL NEVER PROVIDED, in any session.** This session used an inferred minimal stand-in (`LLMCallFailed(Exception)`, `LLMSchemaViolation(Exception)` with `raw_response`/`validation_errors` kwargs) built purely from how `client.py` constructs these exceptions. Every `except (LLMCallFailed, LLMSchemaViolation)` block added this session works structurally regardless of the real file's exact contents (same class names, same `except` clause), but this is flagged as the second-highest-priority file to send next — see CLAUDE.md. |

**FIX (this session, verified):** `generation/content_generator.py` and
`conversation/actions.py` used to import `groq`/`google.genai` directly
— a rule #3 violation in two files, not one. Both rewritten to call
`llm.client.call_gemini`/`call_groq`. Verified via three real scenarios:
(1) clean single-call success, (2) real schema violation on the primary
provider correctly triggering the fallback, (3) both providers failing
correctly degrading to unchanged posts / template fallback rather than
crashing or corrupting data.

**Two files remain outside the gateway, confirmed deliberate, not
violations:** `orchestration/conversation_agent.py` and
`research/routing/llm_router.py` both call `groq.Groq` directly for
tool-calling / plain-text-array use cases the gateway's own docstring
says aren't spec'd against it yet ("ask before assuming"). Reviewed
this session, left as-is.

---

### `generation/`
**STATUS: real generation logic now verified via actual execution for
the first time in this project's session history.** Every prior
session's tests used lightweight stand-ins for `content_generator.py`
specifically because its own logic was in scope. This session tested
the real file.

| File | What changed / was verified |
|---|---|
| `content_generator.py` | **Rewritten (gateway compliance) and verified.** `_select_best_items`'s Pass-1 selection and the main generation call both route through `llm/client.py` now. Confirmed: Pass-1 selection is correctly SKIPPED entirely when `content_intent == "educate"` (verified as a side effect of Scenario C's test design — this is real, existing behavior, not something changed this session). Confirmed: `state["fetched_data"]` is mutated in place by both the topic filter and Pass-1 selection when they DO run — this is safe inside the graph (see `workflow/nodes.py`'s reducer discipline) but was NOT safe in the non-graph retry loop until this session's fix (see `orchestration/` entry below) — proven with an explicit before/after (candidate pool 15→2→2 without the fix, 15→15→15 with it). |
| `formatter.py` | **Fixed and verified.** `content_generation_engine == "None"` (both providers failed, template fallback ran) used to be mislabeled as a successful `gemini-3.5-flash` run in the token report. Reproduced the mislabeling with the old code, confirmed the fix now shows `"Template fallback (no LLM — both providers failed validation)"`. |
| `prompts.py` | Dead code (`build_generation_prompt` and its intent-branching, duplicating `prompt_composer.py` + `intents/*.py`) removed. Only `SYSTEM_PROMPT` remains — confirmed it's the only thing any real call site imports. |
| `prompt_composer.py`, `intents/*.py`, `platforms/*.py` | Real source, unmodified. Exercised successfully across every generation test this session. |

**Output contract, confirmed enforced by the real schema now (not just
code-level normalization as in pre-gateway versions):**
```python
{
    "number": int, "title": str, "hook": str,
    "summary": list[str],   # non-empty (enforced by workflow/gates.py, not schema)
    "link": str,
    "caption": str,
    "hashtags": list[str],  # each MUST start with "#" -- now a hard
                             # schema constraint (Hashtag = Annotated[str,
                             # StringConstraints(pattern=r"^#")]), enforced
                             # at the LLM call boundary. A malformed
                             # hashtag from the model is now a real,
                             # observed LLMSchemaViolation, verified this
                             # session, not a theoretical one.
}
```

---

### `workflow/`
| File | Status this session |
|---|---|
| `gates.py` | **New function added and verified:** `evaluate_generation_combined()` extracts the OR-combination logic (`evaluate_post_validation` OR `evaluate_item_kind_match`) that used to live only inline in `node_evaluate_generation`, so both the graph path and the new non-graph retry loop (`orchestration/dispatch.py::_generate_with_validation`) share one implementation. Also removed a redundant local `link_required_intents` that shadowed the module-level `LINK_REQUIRED_INTENTS` constant. Confirmed: real link-hallucination checking (a generated post's link must exist in `fetched_data`, or validation fails) fired correctly and unexpectedly during testing — this is real, working, pre-existing behavior, not something added this session, but it's worth knowing it's this strict when writing future tests against this file. |
| `nodes.py` | `node_evaluate_generation` refactored to call the new shared function instead of duplicating the combination logic inline. Log output and retry-count behavior confirmed unchanged (same log lines, verified by inspection of test output). |
| `graph.py` | Real source, unmodified. Confirmed compiling and executing correctly via real `langgraph` across every full-pipeline test this session. |

---

### `orchestration/`
| File | Status this session |
|---|---|
| `dispatch.py` | **Four confirmed, verified fixes:** (1) `_handle_generate_more`'s hand-built `fetch_state` dict was missing `"logs"`, causing a real `KeyError` the moment the fetcher logs anything — fixed by building it via `create_initial_state()`. (2) `_handle_targeted_refetch` never set `content_intent`, silently using `conversation/actions.py`'s hardcoded `"showcase"` default — now threads the conversation's real `last_content_intent` through, verified via spy instrumentation. (3) `_handle_targeted_refetch` never set `post_count`, silently regenerating a hardcoded 5 posts regardless of batch size — now defaults to the size of the batch being refined, verified (3-post conversation → 3-post refetch, not 5). (4) `_handle_generate_more`'s accumulate branch (Instagram/TikTok/YouTube/Facebook — the platform default) never called `_snapshot_posts()`, breaking `undo` — fixed, verified via `post_history` inspection. **New function, verified:** `_generate_with_validation()` closes the validation-gate gap (see §2) with a critical, proven-necessary reset of `state["fetched_data"]` between retry attempts — without it, the candidate pool available to Pass-1 selection silently shrinks on every retry (proven 15→2→2 without the fix vs. 15→15→15 with it). |
| `conversation_agent.py` | **One confirmed, reproduced-then-fixed bug:** while a confirmation was pending, the old code discarded ANY tool call other than an exact repeat of the pending action or `clarify`, and force-ran the original pending destructive action regardless — reproduced this exact failure with an explicit before/after (temporarily reverted the fix, confirmed a correctly-resolved `undo` call was discarded and `run_new_request` ran instead; restored the fix, confirmed `undo` now dispatches correctly). Regression-checked: normal confirm-and-proceed behavior (model repeats the pending action) is unchanged, still uses the original pending args. |

---

### `conversation/`
| File | Status this session |
|---|---|
| `actions.py` | **Two confirmed, verified fixes:** (1) `_edit_via_gemini`/`_edit_via_groq` bypassed the gateway (same rule #3 violation as `content_generator.py`) — rewritten to use `llm.client` + `llm.schemas.EditSchema`, verified with both a success path (only the targeted post changes, untargeted posts untouched) and a total-failure path (both providers fail → posts unchanged, error surfaced, not silently swallowed). (2) `targeted_refetch()`'s fetch-path dict had the same missing-`"logs"` bug as `dispatch.py`'s `_handle_generate_more` — same fix, same verification method. The `content_intent="showcase"` hardcode flagged across three prior sessions' audits is now an accepted **default parameter value** (used only if no caller passes one) rather than an unconditional override — verified the real conversation intent reaches this function correctly via `orchestration/dispatch.py`'s threading fix above. |

---

### `research/routing/llm_router.py` — reviewed this session, no bug found
Tested both its success path (valid JSON array response → sources
selected and validated against availability) and its failure path
(malformed/prose response → graceful fallback to
`["google_trends", "reddit", "tavily"]`, filtered by availability, no
crash). The `max_tokens=300` / `reasoning_effort="low"` fix already
present in the file (per its own inline FIX comment, addressing the
same reasoning-model token-starvation bug documented elsewhere in this
project's history) was not re-litigated — nothing in this session's
testing contradicts it.

**Dependency chain note:** this file depends on `research/routing/base.py`
(for `BaseRouter`/`validate_sources()`) and `research/routing/registry.py`
(for `get_available_sources()`), neither of which has ever had real
source provided, in any session. This session used inferred stand-ins
for both, built from `ARCHITECTURE.md`'s own prose description ("0
tokens, category→sources map", "checks CONFIG for enabled+credentialed
sources"). `llm_router.py` itself tested clean against these stand-ins,
but that is not the same as testing it against its real dependencies —
see CLAUDE.md's open-items list.

### `pipeline/generate.py` — reviewed this session, no bug found
Confirmed correct as a thin wrapper around `workflow/graph.py::run_graph()`.
Used as the literal entry point for every full-pipeline test this
session; all passed. The three known, deliberately-not-silently-resolved
UX tradeoffs documented in this file's own docstring (live step
progress, verbose log dump, saved-path message — all lost because
`run_graph()`'s 9-key return contract doesn't expose `state["logs"]`)
were not re-litigated this session; they're a `workflow/graph.py`
return-contract decision, out of scope here.

---

## 4. Files never seen, any session (consolidated list)

This list existed in prior versions of this document; it's reproduced
here with this session's additions marked, since it's the fastest way
for the next session to know what's genuinely still unverified versus
what merely wasn't touched this session.

| File | First flagged | This session's status |
|---|---|---|
| `research/fetchers/fetcher_orchestrator.py` | 2 sessions ago | **Elevated to top priority.** This session's largest finding (a real `KeyError: 'logs'` crash in two dispatch paths) depends on an assumption about this file's logging behavior that has never been checked against real source. |
| `llm/errors.py` | Not previously flagged as missing | **New this session.** Every fix this session to `content_generator.py`/`actions.py`/`dispatch.py` catches `LLMCallFailed`/`LLMSchemaViolation`; this session inferred their shape from usage in `llm/client.py` rather than real source. |
| `research/routing/base.py`, `registry.py`, `router_orchestrator.py`, `rule_router.py` | Not previously flagged as missing | Inferred stand-ins used this session, built from `ARCHITECTURE.md` prose. |
| `understanding/prompt_parser.py` | Prior sessions | Stand-in used again this session. |
| `memory/session_store.py` | Prior sessions | Stand-in used again this session. |
| `core/token_tracker.py` | Not previously flagged as missing | Stand-in used this session. |
| `web/redis_store.py` | 2 sessions ago | Untouched, unrelated to this session. |
| `config/*` full contents beyond what was directly exercised | Prior sessions | Untouched, unrelated to this session. |

---

## 5. Testing pattern, extended again this session

Prior sessions established: test against real dependencies where
feasible, not mocks of them; exact-text diff for pure relocations.

**This session's addition: mock only the network boundary, run
everything else for real, and prove negative claims with an explicit
before/after.** Every fix in this session's ledger was verified by a
test that (a) exercises the real installed `langgraph`/`pydantic`/
`groq`/`google-genai` packages, with only `Completions.create` and
`Models.generate_content` monkeypatched at the SDK class level, and (b)
for the highest-stakes fixes, was proven necessary — not just
plausible — by temporarily reverting the fix, re-running the identical
test, confirming it fails the way the bug report predicted, then
restoring the fix and confirming it passes again. This caught one thing
a pure code-review pass would not have: the `fetched_data` reset fix in
`_generate_with_validation()` looked like defensive programming on
inspection, but the before/after run proved it changes real, observable
behavior (15→2→2 vs. 15→15→15) — the kind of claim this project's own
rules (`CLAUDE.md` rule 8: "written-but-unrun code doesn't count as
done") exist to guard against.

Recommend continuing this practice, especially for anything touching
the non-graph retry loop or the confirmation-gate logic — both have
now had a real, reproduced bug found in them across two different
sessions, which suggests these two areas specifically warrant more
suspicion than a first read suggests.