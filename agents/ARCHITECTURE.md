# TrendForge — ARCHITECTURE.md (Canonical Reference)

> **This document supersedes `TrendForge_Architecture_Redesign.md` and
> `TrendForge_Architecture_Redesign_Addendum2.md`.** Those were written as
> a narrative audit trail. This one is written as a lookup table: find
> your file below, do what its entry says, done.

---

## 0. How To Use This Document

**If you are an AI assistant who has been handed one source file plus
this document:**

1. Find that file's entry in §3 below by its path.
2. The entry's **Contract** section tells you everything about what
   calls this file and what this file calls — you do not need to see
   any other file to know the shape of the data crossing this
   boundary. Treat the Contract as fixed unless the Fix Instructions
   say otherwise.
3. The entry's **Fix Instructions** (if present) tell you exactly what
   to change. Make only that change. Do not "improve" other things you
   notice in the file — if something else looks wrong, name it in your
   reply as a separate observation, don't fix it silently.
4. The entry's **Must NOT touch** section lists things that look
   related but belong to a different file's ownership. Do not move
   logic across that boundary on your own judgment.
5. **If the entry says "ask for X before proceeding," stop and ask.**
   Do not guess at the missing file's contents from the name, and do
   not infer its behavior from how it's used elsewhere in the snippet
   you were given. §6 lists every file not yet covered by this
   document at all — if you're asked to touch one of those, ask for it
   by name, don't proceed from assumption.
6. If a fix requires a new shared module (e.g. `llm/client.py`) that
   doesn't exist yet, §2 has its full spec — build it from that spec
   rather than improvising an interface.

---

## 1. Core Principles (apply when a fix isn't explicitly spelled out)

1. **One decision, one owner.** If two files could plausibly make the
   same call, that's a bug, not a feature — one of them should defer
   to the other.
2. **Structural checks are code, semantic checks are prompts.** A
   missing field or a link that doesn't match fetched data is a
   deterministic code check. "Does this title really match what the
   user meant" is a prompt problem — fix it with better examples, not
   a second blind LLM call.
3. **All LLM calls go through `llm/client.py`.** No file imports
   `Groq` or `google.genai` directly except that one module.
4. **Structured output only.** Every LLM call that feeds the pipeline
   uses a schema (`llm/schemas.py`), never prose-then-parse.
5. **CLI code and worker code never share a file.** If a background
   worker path has to import something that also does `print()` or
   `argparse`, that's a sign the shared logic is in the wrong file.

---

## 2. The LLM Gateway — build this first, everything else depends on it

### `llm/client.py` — NEW FILE

**Job:** the only place either SDK is imported. Every other file gets an
LLM response through this module.

**Exact interface every other entry in this document assumes exists:**
```
call_groq(
    system: str, user: str, model: str,
    schema: dict | None = None,      # JSON schema, enforced via response_format
    tools: list | None = None,       # for tool-calling call sites (ConversationAgent)
    temperature: float = 0.0,
    reasoning_effort: str = "low",
) -> LLMResult

call_gemini(
    system: str, user: str, model: str,
    schema: dict | None = None,
    temperature: float = 0.0,
) -> LLMResult

class LLMResult:
    content: dict | str    # validated against `schema` if provided
    tokens_used: int
    raw_response: Any
```

**Behavior contract:**
- If `schema` is provided and the response violates it, raise
  `LLMSchemaViolation` (see `llm/errors.py`) — do **not** attempt
  prose-repair-parsing. Callers decide their own fallback (retry,
  fall back to a rule-based default, or fall back to the other
  provider) — this module never silently guesses.
- Token tracking: this module returns `tokens_used`; it does **not**
  call `add_tokens()` itself — callers still own writing to their own
  state's token category (`"prompt_parsing"`, `"content_generation"`,
  etc.), since only the caller knows which category applies.

### `llm/schemas.py` — NEW FILE

One schema dict per structured call site, named to match the agent that
owns it: `IntentSchema`, `ItemKindCheckSchema`, `SelectionSchema`,
`GeneratedPostsSchema`, `EditSchema`. Full field definitions for each are
in the corresponding `agents/0N_*.md` file (§7) — copy the "Output
schema" block from there verbatim into this file as a JSON-schema dict.

### `llm/errors.py` — NEW FILE
```
class LLMCallFailed(Exception): ...       # network/API failure
class LLMSchemaViolation(Exception): ...  # response didn't match schema
```

---

## 3. Per-File Reference

### `understanding/intent_extractor.py`
- **Job:** decide topic, category, content_intent, item_kind, search
  queries from cleaned user text.
- **Status:** NEEDS FIX
- **Contract — Inputs:** `cleaned_text: str`, `pre_extracted: dict`
  (from `prompt_cleaner.py` — has `detected_platform`,
  `detected_post_count`, `detected_special_requests`)
- **Contract — Outputs:** writes to `TrendForgeState`:
  `core_topic`, `content_intent`, `post_count`, `post_count_explicit`,
  `content_type`, `special_requests`, `item_kind`, `search_queries`,
  `detected_category`. Does **not** write `platform` — that field is
  owned entirely by `prompt_cleaner.py`'s output, merged upstream of
  this file.
- **Fix instructions:**
  1. Delete `_strip_topic_filler`, `TOPIC_FILLER_PATTERN`,
     `TRAILING_WORD_PATTERN` and the call to them in
     `_merge_into_state`. Use `llm.get("core_topic")` directly — the
     LLM already cleans it per the system prompt.
  2. Remove `platform` from the JSON schema/prompt entirely (see
     `agents/02_intent_agent.md` for the full corrected prompt).
  3. Replace `_parse_llm_json` and its call site with
     `llm.client.call_groq(schema=IntentSchema)`. Delete
     `_parse_llm_json` once nothing calls it.
  4. Update the system prompt per `agents/02_intent_agent.md` §"System
     prompt (tightened)" — adds disambiguating examples for rule 5
     (item_kind) and the "don't strip proper nouns" clarification for
     rule 1.
- **Must NOT touch:** `prompt_cleaner.py` (Agent 1's file, unrelated).
- **If unclear, ask for:** `core/state.py` if you need to confirm
  `TrendForgeState`'s exact field names before writing to them.

---

### `understanding/prompt_cleaner.py`
- **Job:** regex/keyword platform + count detection. 0 tokens.
- **Status:** OK — no change.
- **Contract — Outputs:** `detected_platform`, `detected_post_count`,
  `detected_special_requests`, `cleaned_text`, `is_long`.
- **Must NOT touch:** do not add topic-guessing here — that's
  `intent_extractor.py`'s job entirely.

---

### `research/fetchers/fetcher_orchestrator.py`
- **Job:** dispatch to each selected source's fetcher, collect results.
- **Status:** OK structurally — one optional enhancement available.
- **Contract — Inputs:** `state["selected_sources"]: list[str]`
- **Contract — Outputs:** `fetched_data: dict[str, list]`,
  `total_items_fetched: int`, `sources_used: list[str]`
- **Optional enhancement (not a bug, a speed opportunity):** the
  `for source in selected:` loop calls each fetcher sequentially.
  These are independent HTTP calls to unrelated APIs — safe to fan out
  concurrently (thread pool or `asyncio.gather`), since no fetcher's
  output depends on another's. Only caveat: stagger or rate-limit
  GitHub specifically if running all sources at once trips its
  per-second burst limit (separate from its hourly quota).
- **Must NOT touch:** do not reinterpret or rewrite `search_queries` /
  `core_topic` here — that reasoning already happened once, correctly,
  in `intent_extractor.py`. This file's only job is dispatch.
- **If unclear, ask for:** individual fetcher files (`github_fetcher.py`
  etc.) if the parallelization change needs to account for
  fetcher-specific rate-limit behavior not visible in this file alone.

---

### `research/routing/rule_router.py`
- **Job:** deterministic category → sources mapping.
- **Status:** OK — no change.
- **Contract — Inputs:** `detected_category`, `special_requests`
- **Contract — Outputs:** `selected: list[str]`

---

### `research/routing/llm_router.py`
- **Job:** LLM fallback source selection when `RuleRouter.can_handle()`
  returns False.
- **Status:** NEEDS FIX (minor)
- **Fix instructions:** add `"github"` as a candidate in the hardcoded
  fallback list (`["google_trends", "reddit", "tavily"]` →
  `["google_trends", "reddit", "tavily", "github"]`), so tech-category
  requests that hit this fallback path aren't permanently missing
  GitHub as an option.
- **Optional:** route its Groq call through `llm.client.call_groq(...)`
  once that module exists, for consistency — not urgent, this call
  site already handles its own failure gracefully.
- **Must NOT touch:** `rule_router.py` — this file only runs when that
  one declines.

---

### `generation/prompt_composer.py`
- **Job:** the only file that combines an IntentStrategy's guidance with
  a PlatformStrategy's structure into the final generation prompt.
- **Status:** OK — design is correct, no change.
- **Contract — Inputs:** full `TrendForgeState` (topic, intent, platform,
  fetched_data, post_count, retry errors if any)
- **Contract — Outputs:** one prompt string
- **Must NOT touch:** do not make this file branch on
  `content_intent` AND `platform` together anywhere — that's exactly
  the coupling the two-strategy design exists to prevent. If a new
  rule genuinely needs both, it belongs here (this is the one file
  allowed to see both), but as a combination of two independently-owned
  guidance objects, not a new branch.

---

### `generation/content_generator.py`
- **Job:** turn fetched data + intent/platform guidance into final posts.
- **Status:** NEEDS FIX (the largest fix in this document)
- **Contract — Inputs:** `TrendForgeState` after fetch + gate-pass
- **Contract — Outputs:** `generated_posts: list[dict]`,
  `content_generation_engine: str`, `leftover_fetch_pool: list`
- **Fix instructions:**
  1. **Delete the keyword-substring topic filter** (the block starting
     `if topic and content_intent != "educate": topic_words = ...`).
     It re-decides relevance after `FetchQualityGate` already passed
     the data, and can silently shrink the pool below the quality
     floor with nothing re-checking.
  2. **Delete `_select_best_items` and the Pass-1 regroup step
     entirely — do not extract it into its own file.** (Revised from
     an earlier version of this document that recommended formalizing
     it as a separate agent; see `agents/10_selection_agent.md` for
     the full reasoning behind this reversal.) `prompt_composer.py`
     already shows the main generation call comparable coverage of
     the fetched data, so a separate selection round trip is redundant
     work, not a reliability improvement. Instead: stop regrouping
     `fetched_data` to a pre-selected subset before calling
     `compose_prompt()` — pass the full quality-gate-passed set
     through. Bump `prompt_composer.py`'s per-source item cap
     (currently `items[:5]`) slightly so the model has genuine choice,
     and add one line to the core instructions asking it to select the
     best `{post_count}` from what it's shown before writing. No new
     schema needed.
  3. Replace `_call_groq_fallback`, the direct
     `genai.Client(...)` construction, and `_parse_json` with calls
     through `llm.client.call_gemini(...)` /
     `llm.client.call_groq(...)`. Delete `_parse_json` and
     `_build_fallback_posts`'s dependency on manual parsing once this
     is done (keep `_build_fallback_posts` itself — see note below).
  4. Add a schema pattern constraint (`"pattern": "^#"`) to the
     hashtags field in `GeneratedPostsSchema` instead of the manual
     `t if t.startswith("#") else f"#{t}"` normalization loop — delete
     that loop once the schema enforces it.
  5. Keep `_build_fallback_posts` as the last-resort path when both
     providers fail — but confirm (ask for `generation/formatter.py`
     if needed) whether `content_generation_engine == "None"` is
     surfaced to the end user anywhere. If not, that's a gap to flag,
     not necessarily to fix in this file.
- **Must NOT touch:** `prompt_composer.py`'s prompt-assembly logic —
  this file calls `compose_prompt()`, it doesn't duplicate what's
  inside it.
- **If unclear, ask for:** `generation/formatter.py` (to check the
  fallback-visibility question above), `core/state.py` (exact
  `TrendForgeState` shape).

---

### `workflow/gates.py`
- **Job:** `evaluate_fetch_quality`, `evaluate_post_validation`,
  `evaluate_item_kind_match` — see `agents/04, 06, 07` for full specs.
- **Status:** NEEDS FIX (small)
- **Contract:** unchanged — see the three agent files for exact
  input/output shape per function.
- **Fix instructions:** in `evaluate_item_kind_match`, replace the
  inline `Groq(...)` client construction with
  `llm.client.call_groq(schema=ItemKindCheckSchema)`. No other change —
  `evaluate_fetch_quality` and `evaluate_post_validation` are already
  correctly deterministic/code-only and need nothing.
- **Must NOT touch:** do not add new semantic (LLM-based) checks to
  `evaluate_fetch_quality` or `evaluate_post_validation` — if a new
  check needs judgment rather than a fact comparison, it's a new,
  separately-named agent, not an addition to these two functions.

---

### `workflow/graph.py` + `workflow/nodes.py`
- **Job:** LangGraph implementation of fetch→generate with retry loops.
- **Status:** NEEDS FIX (this is the canonical pipeline going forward —
  see `agents/00_graph_wiring.md` for the full corrected design)
- **Fix instructions:** three changes, all detailed in
  `agents/00_graph_wiring.md`:
  1. `node_evaluate_generation` must call both
     `evaluate_post_validation` AND `evaluate_item_kind_match`,
     combined — today it only calls the first.
  2. `fetched_data` becomes a state channel with a custom merge
     reducer (`Annotated[dict, merge_fetched_data]` in
     `core/state.py`) instead of being overwritten on each retry loop
     back through `fetch`.
  3. Delete `GRAPH_TIMEOUT_SECONDS` and the `ThreadPoolExecutor`
     wrapper in `run_graph()` — the RQ job's own `job_timeout=180`
     (set in `api/web/app.py`) already owns this.
- **Scope:** this graph only drives `run_new_request` and
  `generate_more`. Do not add nodes for `edit_existing`, `undo`,
  `add_constraint`, `remove_constraint`, or `targeted_refetch` — those
  stay as direct function calls in `orchestration/dispatch.py` (§4).
- **If unclear, ask for:** `core/state.py` before implementing the
  custom reducer, to see the exact current `TrendForgeState` TypedDict
  definition.

---

### `main.py`
- **Job today:** everything — pipeline, dispatch, CLI. **Job after
  fix:** CLI entrypoint only.
- **Status:** NEEDS SPLIT — see §4 for the three resulting files.
- **Fix instructions:** move `run()` to `pipeline/generate.py`
  (rewritten as a thin call into the compiled graph, not the current
  procedural loop). Move `dispatch_action` and all `_handle_*`
  functions to `orchestration/dispatch.py`. What remains in `main.py`:
  `interactive_mode`, `print_banner`, `_extract_flags`, the
  `argparse` entrypoint. Nothing else.
- **Must NOT touch:** don't leave any function partially in both
  places — each moved function goes entirely to its new file, no
  re-exporting shims left behind "for compatibility."

---

### `conversation/orchestrator.py` → `orchestration/conversation_agent.py`
- **Job:** decide which of 8 actions a chat turn maps to; own the
  destructive-action confirmation gate.
- **Status:** NEEDS FIX (this is the one live safety bug in the
  codebase, not just a maintainability issue — see
  `agents/08_conversation_agent.md`)
- **Contract:** unchanged, see agent file for full input/output shape.
- **Fix instructions:**
  1. Rename file/move to `orchestration/conversation_agent.py`.
  2. The invalid-tool-call branch and the top-level
     `except Exception` branch in `process_turn` both currently
     `return fallback` (= `run_new_request`) without passing through
     the `DESTRUCTIVE_ACTIONS` confirmation check. Fix: every return
     path that could resolve to `run_new_request` — clean success,
     malformed args, exception — must pass through the same
     confirmation check before returning. No exceptions.
  3. Route the Groq calls (`process_turn`, `maybe_summarize`) through
     `llm.client.call_groq(...)`.
- **Must NOT touch:** the pending-confirmation resume logic (using the
  originally-stored `pending["action"]`/`pending["args"]`
  deterministically rather than re-deriving) — that part is already
  correct, don't change it.

---

### `conversation/actions.py`
- **Job:** pure action implementations — `edit_existing`,
  `add_constraint`, `remove_constraint`, `targeted_refetch`.
- **Status:** NEEDS FIX
- **Fix instructions:**
  1. `targeted_refetch(topic_delta, current_topic, leftover_fetch_pool,
     active_constraints)` hardcodes `"content_intent": "showcase"` in
     both its internal `evaluate_fetch_quality` check and its fetcher
     call. Add a `content_intent` parameter and use it in both places
     instead — the caller already has `last_content_intent` available.
  2. Replace `_edit_via_gemini` / `_edit_via_groq`'s direct client
     construction with `llm.client.call_gemini(...)` /
     `llm.client.call_groq(...)`. Drop the dependency on
     `generation.content_generator._parse_json` — use the schema-
     enforced result from the gateway instead (define `EditSchema` in
     `llm/schemas.py`: same shape as `GeneratedPostsSchema` but no
     `series_hook`/`trend_insight`).
- **Must NOT touch:** the error-signaling contract (`{"edited_posts":
  ..., "tokens_used": ..., "error": ...}`) — `main.py`'s
  `_handle_edit_existing` (moving to `orchestration/dispatch.py`)
  depends on `error` being `None` vs a string exactly as it is today.

---

### `api/web/handlers.py`
- **Job:** bridge between the web/worker layer and action dispatch.
- **Status:** NEEDS FIX (one line)
- **Fix instructions:** change `import main` to
  `import orchestration.dispatch as dispatch`, and
  `main.dispatch_action(...)` to `dispatch.dispatch_action(...)`.
  Nothing else in this file changes — `finalize_turn`'s two
  housekeeping calls (`update_last_tool_result`,
  `maybe_summarize`) stay exactly as they are, just update their
  import path to `orchestration.conversation_agent`.
- **Must NOT touch:** the function's return contract
  (`conversation.get("last_output") or ""`).

---

### `api/web/app.py`, `api/web/jobs.py`, `api/web/worker.py`
- **Status:** OK — no change needed for anything covered so far.
- **Note for future work:** `app.py`'s `job_timeout=180` on the
  `_queue.enqueue(...)` call is the single timeout that now governs
  the whole pipeline once `workflow/graph.py`'s own timeout is removed
  (see that entry above) — if this value ever changes, that's the only
  place to change it.

---

### `memory/redis_session_store.py`
- **Job:** live conversation cache (Redis, write-through to Postgres).
- **Status:** OK — no change. This is the real, correct conversation
  store — confirmed by matching its `_DEFAULT_CONVERSATION` shape
  against every field `orchestration/conversation_agent.py` and
  `orchestration/dispatch.py` actually read/write.

---

### `memory/session_store.py`
- **Job:** permanent, unbounded JSON history (`get_already_covered`,
  `save_session`).
- **Status:** OK — no change. Intentionally separate concern from
  `redis_session_store.py` — do not merge these two files.

---

### `web/redis_store.py`
- **Status:** DELETE.
- **Reason:** a second, incompatible conversation-store implementation.
  Broken as written (`import api.web.redis_store as redis_store` then
  treats the alias as the `redis` package — this cannot run). No
  `client_name` in its key shape, meaning zero user isolation if it
  were ever wired in. Missing `pending_confirmation` entirely, which
  would silently disable the destructive-action confirmation gate.
- **Before deleting:** search the repo for any import of
  `web.redis_store` — if genuinely unreferenced, delete outright; if
  something imports it, that call site needs to be repointed at
  `memory/redis_session_store.py` first.

---

### `generation/intents/base_intent.py`, `generation/platforms/base_platform.py`
- **Status:** OK — no change. Two-axis Strategy Pattern is correctly
  isolated; neither file branches on the other's dimension.

---

## 4. New Files To Create

### `pipeline/generate.py`
- **Job:** thin wrapper around the compiled LangGraph pipeline —
  replaces `main.py`'s old procedural `run()`.
- **Contract:**
```
def run(prompt: str, platform: str | None = None, post_count: int = 5) -> dict:
    # builds initial state, invokes the compiled graph from workflow/graph.py,
    # returns the same 9-key contract main.py:run() used to return:
    # output, session_id, tokens, total_tokens, errors, posts, topic,
    # platform, content_intent
```
- **Calls:** `workflow.graph` (compiled graph), `core.state`.
- **Called by:** `orchestration/dispatch.py`'s `_handle_run_new_request`
  and `_handle_generate_more`.

### `orchestration/dispatch.py`
- **Job:** `dispatch_action` + all 8 `_handle_*` functions, moved
  verbatim from `main.py` except: `_handle_run_new_request` and
  `_handle_generate_more` now call `pipeline.generate.run(...)`
  instead of the old procedural loop; all `print()` calls are removed
  (this runs inside the RQ worker, which has no terminal).
- **Contract:** `dispatch_action(action, args, conversation, verbose,
  prompt="", platform=None, posts=5) -> None` (mutates `conversation`
  in place, same as today).
- **Fix from the original audit:** the unknown-action fallback
  (`handlers.get(action)` returning `None`) must default to
  `clarify`, not `run_new_request` — same reasoning as the
  confirmation-gate fix in `orchestration/conversation_agent.py`.
- **Called by:** `api/web/handlers.py::finalize_turn`, `main.py`'s
  `interactive_mode`.

---

## 5. Confirmed Correct — No Action, Full List

`generation/prompt_composer.py`, `understanding/prompt_cleaner.py`,
`research/routing/rule_router.py`,
`generation/intents/base_intent.py`,
`generation/platforms/base_platform.py`,
`memory/redis_session_store.py`, `memory/session_store.py`,
`api/web/app.py`, `api/web/jobs.py`, `api/web/worker.py`.

---

## 6. Not Yet Audited — Ask For These By Name Before Touching

If a task requires changing any of the following, this document does
not yet cover them — request the actual file rather than inferring its
contract from how it's referenced elsewhere:

`core/state.py`, `config/` (all files),
`generation/formatter.py`, `generation/prompts.py`,
`generation/intents/*.py` (individual strategies — only the base class
is covered), `generation/platforms/*.py` (same),
`research/fetchers/github_fetcher.py` and all other individual
fetchers, `research/routing/router_orchestrator.py`,
`research/routing/registry.py`, `research/routing/base.py`,
`api/web/auth.py`, `api/web/db.py`, `api/web/deps.py`,
`api/web/rate_limit.py`, `api/web/anon_trial.py`,
`api/web/schemas.py`, `frontend/` (all files).

---

## 7. Cross-References

Full LLM prompts, schemas, and "must not do" reasoning for every
LLM-backed decision in the system live in `agents/00` through `10`:

`00_graph_wiring.md`, `01_prompt_cleaner_agent.md`,
`02_intent_agent.md`, `03_router_agent.md`,
`04_fetch_quality_gate.md`, `05_generation_agent.md`,
`06_post_validation_gate.md`, `07_item_kind_gate.md`,
`08_conversation_agent.md`, `09_summarizer_agent.md`,
`10_selection_agent.md`.

If your task touches a file listed in §3 above and you need the exact
system prompt or schema referenced there, that's in the matching
`agents/0N_*.md` file — check there before asking, it's already written.

---

## 8. Performance & Resilience

Full detail in `PERFORMANCE_AND_RESILIENCE.md`. Summary of the changes
it specifies, each tied to a §3 entry above:

- Parallel fetch fan-out (`fetcher_orchestrator.py`, already noted
  there as an optional enhancement).
- Category detection moved to the deterministic rule-based step
  (`prompt_cleaner.py`) so `RouterAgent` can run concurrently with
  `IntentAgent` instead of waiting on its LLM output.
- `SelectionAgent` merged into `GenerationAgent` — see the revised
  `content_generator.py` entry above.
- `ItemKindGate` made conditionally-skippable for `generate_more`
  specifically (optional, stakes-based).
- `maybe_summarize` deferred out of the synchronous reply path.
- The general framework for adding new error handling without an
  ever-growing pile of one-off functions: a gate registry for
  deterministic checks, prompt examples + a regression set for semantic
  misjudgments, and a single centralized retry policy in
  `llm/client.py` for transient/systemic failures. An explicit
  argument against building a generic LLM-based "error recovery agent"
  is included there too — read it before reaching for that pattern.
