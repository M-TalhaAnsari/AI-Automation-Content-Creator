# CLAUDE.md — TrendForge Session Handoff

> Paste this whole file into a new session as the first message.
>
> **This is the third handoff.** It supersedes the second CLAUDE.md's
> status ledger entirely. The defining difference from every prior
> session: this one did not review source and reason about it in the
> abstract. Every fix below was applied to a real reconstructed copy of
> the project (real `pydantic`, real `langgraph`, real `groq`/`google-genai`
> SDKs, network calls mocked at the SDK boundary) and *executed*, with
> before/after comparisons proving each bug was real and each fix
> actually closes it. Where something is still a proposed diff rather
than a verified fix, that's called out explicitly below — don't assume
> silence means untested.

## What this is

TrendForge is a multi-agent AI pipeline that turns a raw user prompt
into finished social media posts — understand intent → route to
sources → fetch real data → generate posts → validate → format.
LangGraph drives the fetch/generate retry loop; conversational actions
(`generate_more`, `edit_existing`, `targeted_refetch`, etc.) are direct
dispatch, outside the graph.

## Reading order for a new session

1. **This file** — status, rules, what to ask for.
2. **`FLOW.md`** — the pipeline graph, node by node, build status.
3. **`ARCHITECTURE.md`** — canonical per-file lookup table.

## Non-negotiable rules (unchanged, reconfirmed this session)

1. One decision, one owner.
2. Structural checks are code; semantic checks are prompts.
3. All LLM calls go through `llm/client.py`. No other file imports
   `groq` or `google.genai` **for content-affecting generation calls**.
   Two exceptions are known and deliberate, not violations:
   `orchestration/conversation_agent.py` (tool-calling, not yet spec'd
   against the gateway — see `llm/client.py`'s own docstring) and
   `research/routing/llm_router.py` (same reason). Both were reviewed
   this session and left as-is.
4. Structured output only.
5. CLI code and worker code never share a file.
6. Schemas in `llm/schemas.py` are Pydantic models; `llm/client.py`
   always locally re-validates via `model_validate_json()`.
7. `LLMResult.content` stays a plain dict at the boundary.
8. **Every new/rewritten file gets sanity-tested before being handed
   over.** This session went further than "tested against a real
   dependency" — every fix below was tested against the full real
   stack (real langgraph graph compiled and invoked, real pydantic
   schema validation, real retry/backoff logic in `llm/client.py`
   actually executing its sleep-and-retry loop) with only the outbound
   network call mocked. Several fixes were proven with an explicit
   before/after: the bug was reproduced by temporarily reverting the
   fix and re-running the same test, then the fix was restored and
   re-verified. That distinction (theorized bug vs. reproduced-then-fixed
   bug) is marked per item below.
9. Reducer-owned state fields (`fetched_data`) must be excluded from
   any node's return value unless that node owns the field — see
   `core/state.py::state_without_reducer_keys()`. Confirmed correct in
   `workflow/nodes.py` again this session (unmodified, verified via
   real langgraph execution, not just re-asserted).

## Status ledger

### ✅ Done AND empirically verified this session (bug reproduced, fix confirmed to close it)

| Item | File(s) | How it was verified |
|---|---|---|
| **`generate_more`/`targeted_refetch` crash with `KeyError: 'logs'`** | `orchestration/dispatch.py::_handle_generate_more`, `conversation/actions.py::targeted_refetch` | **New finding this session, found only by running the code — not previously flagged in any prior session's audit.** Both built a bare 6-key dict (`{"errors": [], ...}`, no `"logs"`) as the state object passed to `FetcherOrchestrator().fetch()`, instead of `create_initial_state()`. The instant the fetcher calls `add_log()` — the same shared helper every other module in this codebase uses — this raises `KeyError`. Reproduced against a real fetcher stand-in that logs (matching the pattern every other real module in this codebase follows). Fixed by building these state objects via `create_initial_state()` and overlaying only the fields that differ, guaranteeing every key `add_log`/`add_error`/`add_tokens` expects is present. **This is very likely a real, currently-live crash in production** — confirm by checking whether the real `research/fetchers/fetcher_orchestrator.py` calls `add_log`/`add_error` anywhere (near-certain, given the codebase's consistent pattern, but not yet directly confirmed against that file's real source). |
| **`content_generator.py`/`conversation/actions.py` bypassed the LLM gateway** | `generation/content_generator.py`, `conversation/actions.py` | Rewritten to route through `llm/client.py` using `llm/schemas.py`'s `GeneratedPostsSchema`/`EditSchema`. Verified: (a) clean happy path produces valid posts via one Gemini call; (b) a real `LLMSchemaViolation` (bad hashtag missing `#`) is raised, caught, and triggers the Groq fallback — confirmed via the actual pydantic validation error text, not a simulated exception; (c) both providers failing degrades to `_build_fallback_posts()` / unchanged posts, never crashes, never silently corrupts data. |
| **`formatter.py` mislabels total-failure runs as successful Gemini generations** | `generation/formatter.py` | Reproduced: forced both providers to fail schema validation, confirmed `content_generation_engine` was `"None"`, confirmed the OLD label logic would have shown `gemini-3.5-flash`. Fix verified to show `"Template fallback (no LLM — both providers failed validation)"` instead. |
| **`conversation_agent.py` pending-confirmation override bug — confirmed live, not just plausible** | `orchestration/conversation_agent.py::process_turn` | **Reproduced with an explicit before/after.** Old code: user replies to a pending destructive-action confirmation with something that resolves to a *different* legitimate action (e.g. "wait no, undo that instead" → model correctly calls `undo`); old code discarded that tool call and force-ran the original pending `run_new_request` anyway — reproduced this exact behavior by temporarily reverting to the original block and re-running the test, confirmed `action` came back as `run_new_request` instead of `undo`. Fix (only an exact repeat of the pending action counts as confirmation) verified to correctly dispatch `undo` instead. Regression-checked: normal confirm-and-proceed (model repeats the same pending action) still works and still uses the *original* pending args, not the new turn's. |
| **`generate_more`/`targeted_refetch` had zero validation-gate enforcement** | `orchestration/dispatch.py` (new `_generate_with_validation`), `workflow/gates.py` (new `evaluate_generation_combined`), `workflow/nodes.py` (refactored to call it) | Verified with a real forced failure: first generation attempt has duplicate titles (fails `evaluate_post_validation` for real), retry loop catches it, second attempt is clean, dispatch succeeds — confirmed via call-count assertion (exactly 2 `GeneratedPostsSchema` calls, not 1). Also confirmed the retry cap works: a scenario where validation never passes correctly stops at `MAX_GENERATION_RETRIES` (3 total attempts) and proceeds with best-effort output rather than looping forever. |
| **Non-graph retry loop would have silently shrunk its own candidate pool across retries** | `orchestration/dispatch.py::_generate_with_validation`'s `fetched_data` reset | **Reproduced with an explicit before/after — this is the single most important confirmed finding this session.** With the reset removed: candidate pool went 15 → 2 → 2 across three retry attempts (Pass-1 selection shrank it to `target_count=2` on attempt 1; attempt 2 then saw the *already-shrunk* pool and, since `2` is not `> target_count`, skipped re-selecting — so the retry was drawing from a stale, artificially narrow set instead of the real fetched data). With the reset restored: pool stayed at 15 for all three attempts, exactly as intended. This confirms the reset is load-bearing, not defensive-programming theater. |
| **`generate_more`'s accumulate branch never snapshotted for `undo`** | `orchestration/dispatch.py::_handle_generate_more` | Verified: after a `generate_more` call on an accumulating platform (Instagram), `conversation["post_history"]` correctly contains exactly one entry holding the pre-append post count — confirming `undo` would restore the right state. |
| **`targeted_refetch` silently regenerated a hardcoded 5 posts regardless of batch size** | `orchestration/dispatch.py::_handle_targeted_refetch` | Verified: a 3-post conversation run through `targeted_refetch` produced exactly 3 posts, not 5. |
| **`targeted_refetch`'s `content_intent="showcase"` hardcode — the bug flagged across every prior session's audit** | `conversation/actions.py::targeted_refetch`, `orchestration/dispatch.py::_handle_targeted_refetch` | **This is the first session that actually verified the fix, not just applied it.** Instrumented `conversation.actions.targeted_refetch` with a spy to capture the literal `content_intent` value it received when the conversation's real intent was `"inspire"` (deliberately not `"showcase"`, to rule out a false pass) — confirmed `"inspire"` reached the function, not the old hardcoded default. |
| **`workflow/gates.py` had a duplicate/redundant `link_required_intents` local var shadowing the module-level constant** | `workflow/gates.py` | Removed; `evaluate_post_validation` now references the single `LINK_REQUIRED_INTENTS` constant. Low-risk cleanup, covered incidentally by every generation test above (link-requirement checks still fire correctly). |
| **`generation/prompts.py` dead code (near-duplicate of `prompt_composer.py` + `intents/*.py`)** | `generation/prompts.py` | Removed everything except `SYSTEM_PROMPT`, which is the only thing any real call site imports. Confirmed nothing else in the reconstructed project imports `build_generation_prompt`. |
| **`research/routing/llm_router.py` (the file provided this session)** | `research/routing/llm_router.py` | **No bug found.** Tested both its raw-JSON-array success path and a malformed-response path (model returns prose instead of JSON) — both work correctly, fallback list returned without crashing. The `max_tokens=300`/`reasoning_effort="low"` fix already present in the file (per its own inline comment) was not re-litigated; nothing in this session's testing contradicts it. |
| **`pipeline/generate.py` (the file provided this session)** | `pipeline/generate.py` | **No bug found.** Confirmed it's a correct thin wrapper around `workflow/graph.py::run_graph()` and that the 9-key return contract lines up — used as the entry point for every full-pipeline test this session (Scenario A/B), all passed. |

### ✅ Confirmed correct via real execution, unmodified (not just re-asserted from a prior session's claim)

- `workflow/graph.py` — real `StateGraph` compiled and invoked successfully across every test this session, including the fetch-retry and generation-retry conditional edges.
- `workflow/nodes.py`'s `state_without_reducer_keys()` discipline — no duplication observed across any multi-retry test.
- `core/state.py`'s `merge_fetched_data` reducer — no double-counting observed.
- `Config/__init__.py` / `Config/config.py`'s casing (`Config`, capital C) — confirmed correct against real source in a prior session; not re-litigated here, no issue found.

### 🔴 NOT verified this session — still exactly as prior sessions left them

These were out of scope for this session's actual-execution pass because their real source has never been provided, in any session:

| File | Why it matters | What's needed |
|---|---|---|
| `research/fetchers/fetcher_orchestrator.py` | **This session's biggest open risk.** Every test this session ran against a hand-built stand-in (clearly labeled as such in the sandbox, not real source) that returns fabricated items and calls `add_log`. If the REAL file does not call `add_log`/`add_error` the way every other module in this codebase does, the `KeyError: 'logs'` finding above may not apply as described — though the underlying issue (a hand-built partial state dict, missing keys the shared `core.state` helpers assume) would still be worth checking directly. Send this file next session to confirm or rule out. |
| `generation/formatter.py`'s `core.token_tracker.TokenTracker` | Tested against a hand-built stand-in this session. Real `TokenTracker.generate_report()` signature/behavior unverified. |
| `understanding/prompt_parser.py` | Tested against a hand-built stand-in. Real intent/platform/category detection logic unverified. |
| `research/routing/base.py`, `registry.py`, `router_orchestrator.py`, `rule_router.py` | All hand-built stand-ins this session, inferred from `ARCHITECTURE.md`'s prose descriptions, not real source. `research/routing/llm_router.py` itself (the one real file provided) tested clean against these stand-ins, but the stand-ins themselves are unverified. |
| `memory/session_store.py` | Stand-in only (`get_already_covered` returns `[]`, `save_session` no-ops). |
| `llm/errors.py` | **Never provided in any session.** This session inferred a minimal `LLMCallFailed`/`LLMSchemaViolation` implementation purely from how `llm/client.py` constructs them, clearly labeled as a sandbox stand-in in that session's work. If the real file's constructor signature differs (e.g. different kwarg names), every `except (LLMCallFailed, LLMSchemaViolation)` block across `content_generator.py`/`actions.py`/`dispatch.py` still works structurally (same exception classes, same `except` clause), but any code that reads `.raw_response`/`.validation_errors` off a caught exception should be checked against the real file. |
| `web/redis_store.py` deletion | Still not actioned, still not touched — carried forward from two sessions ago, unrelated to this session's work. |
| CLI-timeout decision in `pipeline/generate.py`/`workflow/graph.py` | Still not decided — carried forward, unrelated to this session's work. |
| `run_graph()`'s 9-key return contract (no `logs`/`saved_path`) | Still not decided — carried forward, unrelated to this session's work. |
| `config/*` full audit | Still not done — carried forward. |

## What to literally paste into the next session

At minimum: this file, `FLOW.md`, `ARCHITECTURE.md`.

**Top priority send: `research/fetchers/fetcher_orchestrator.py`.** This
session's single largest finding (`KeyError: 'logs'` in two dispatch
paths) is very likely real, but its confirmation rests on an assumption
about that file's logging behavior that has never been checked against
actual source, in any session across this whole project's history. That
makes it simultaneously the most valuable and least-verified finding on
this ledger — resolve that gap first.

Second priority: `llm/errors.py` — the one file this session had to
infer from usage rather than real source, specifically because every
fix this session made to `content_generator.py`/`actions.py`/`dispatch.py`
depends on catching `LLMCallFailed`/`LLMSchemaViolation` correctly.

## Recommended next action

1. **Send `research/fetchers/fetcher_orchestrator.py` and `llm/errors.py`.** Closes the two highest-value open unknowns from this session with the least effort — both are small, targeted asks, not another full-module audit.
2. **Re-run this session's `KeyError: 'logs'` fix against the real fetcher** once received, to convert "very likely real" into "confirmed real," or rule it out cleanly if the real file doesn't log the way assumed.
3. Everything else on the 🔴 list is lower-urgency and can wait — none of it blocks correctness of what's already fixed and verified.

---

## ADDENDUM — second pass, same session, after direct scrutiny of `content_generator.py`

The person reviewing this work asked, directly and rightly, why
`content_generator.py` had "a lot changed" beyond the stated gateway-
compliance task, and asked for the unvarnished assessment rather than a
defense of the original diff. That review found two more real issues —
one a genuine regression that's now fixed at the root cause, one
unjustified scope creep that's now reverted. Both were verified
empirically (bug reproduced, fix confirmed to close it, full regression
re-run clean), consistent with this session's overall practice — not
just patched and asserted.

### ✅ Found and fixed this pass

| Item | What was wrong | Fix | Verification |
|---|---|---|---|
| **Exception-handling narrowed too far in `content_generator.py`** | Rewriting to route through the gateway also narrowed `except Exception` to `except (LLMCallFailed, LLMSchemaViolation)`. But `llm/client.py`'s `_lazy_genai_client()`/`_lazy_groq_client()` construct SDK clients **outside** the retry wrapper — a construction-time failure (bad key format, SDK-internal error) escaped as a raw, unwrapped exception type, not one of the two documented types. | Fixed at the root in `llm/client.py`: `call_groq`/`call_gemini` now wrap client construction in try/except, re-raising as `LLMCallFailed`. This restores the gateway's own documented contract for *every* caller, not just a local patch in one file. | Reproduced: simulated a broken Gemini client, confirmed `ContentGenerator().generate()` crashed uncaught, confirmed the crash propagated through `dispatch.py`'s non-graph path with no safety net (unlike `node_generate`'s broader catch in the graph path) — a real user-facing `generate_more` request would have crashed instead of degrading gracefully. Fixed, re-tested: no crash, clean fallback, verified end-to-end. |
| **Unjustified temperature changes in `content_generator.py`** | The gateway rewrite also silently changed generation temperature: Pass-1 selection from (unset/0.2) to `routing_temperature` (0.0), and — more seriously — main generation's Groq fallback from a hardcoded `0.2` to `generation_temperature` (0.85), a 4x jump on the specific path meant to run when the primary provider already failed. These are real config fields that already existed in `Config/config.py` (not invented), but the file choosing to start using them was an unannounced product/creative-output decision, not a gateway-compliance requirement. | Reverted all four call sites to `0.2` — the one concrete temperature value that ever existed in the original file. The two originally-*unset* Gemini calls can't have "provider default" faithfully reproduced through this gateway (it always sends an explicit temperature), so `0.2` was chosen there too, matching each call's own Groq-fallback sibling rather than introducing a third, different guessed number. This is flagged inline in the file itself as a known, deliberate, lowest-risk choice — not a resolved product decision. | Confirmed via direct diff against the original source (re-transcribed exactly, not re-derived from memory) that `0.2` is the only value that ever appeared in the file, and that it's now used uniformly. Full regression suite re-run clean after the revert. |
| **Tokens silently lost on schema-validation failure** | `llm/client.py`'s `_validate()` raises `LLMSchemaViolation` *before* an `LLMResult` is ever constructed — meaning real API tokens spent generating an invalid response were completely unrecoverable by any caller, in `content_generator.py`, `conversation/actions.py`, or anywhere else. Confirmed empirically before fixing (forced a schema violation, confirmed `getattr(exc, "tokens_used", ...)` was `<NOT PRESENT>`). | `_validate()` now attaches `tokens_used` to the exception via a plain attribute set after construction (`exc.tokens_used = tokens_used`), **not** a constructor parameter — deliberate, since `llm/errors.py`'s real source has never been provided in any session, and this approach works regardless of that file's actual `__init__` signature. `content_generator.py` and `conversation/actions.py`'s `edit_existing` both updated to read this via `getattr(e, "tokens_used", 0)` in their except blocks and record it, opt-in, rather than losing it. | Confirmed empirically both ways: before the fix, the attribute was absent; after, it correctly returns the mocked token count (`200`). Full regression suite re-run clean. |

### What this second pass changed, concretely

- `llm/client.py`: client-construction wrapped in try/except → `LLMCallFailed`; `_validate()` now takes a `tokens_used` param and attaches it to any raised `LLMSchemaViolation`.
- `generation/content_generator.py`: all four temperature values reverted to `0.2`; both except blocks (Pass-1 selection and main generation) now capture `tokens_used` off caught exceptions via `getattr`.
- `conversation/actions.py`: `edit_existing`'s except blocks do the same token capture.

All three files re-verified against the full 10-file test suite (adds two new tests this pass: one reproducing-then-fixing the exception-narrowing crash, one reproducing-then-fixing the token loss) — all pass. Nothing else in the previously-delivered ledger was touched or needs re-verification as a result of this pass.

### Still open, unchanged by this pass

Everything in the original 🔴 list above still applies exactly as written — `fetcher_orchestrator.py` and `llm/errors.py` remain the two highest-priority sends. This pass didn't reduce that list; it found and closed two issues *within* files already delivered this session, caught only because the person reviewing pushed for a harder look rather than accepting the first pass's self-assessment at face value. Worth normalizing that as standard practice going forward: a file being "gateway-compliant now" doesn't mean every line that changed to get there was necessary, and doesn't mean the file's failure modes were fully re-derived rather than assumed to still work like the original.