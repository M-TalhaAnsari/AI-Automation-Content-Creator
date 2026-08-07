# TrendForge — Architecture Redesign

> This document replaces the orchestration/prompt-layer sections of your existing
> `ARCHITECTURE.md`. It is the output of a full audit of `conversation/orchestrator.py`,
> `understanding/intent_extractor.py`, `generation/prompt_composer.py`, `workflow/gates.py`,
> `workflow/graph.py` + `nodes.py`, `main.py`, `api/web/app.py`, `api/web/jobs.py`,
> `api/web/handlers.py`, and `api/web/worker.py`.

---

## 1. Root Cause, Stated Once

Every bug found in this audit is the same bug wearing a different costume:

**A decision gets made by one mechanism, and a second, disconnected mechanism
re-makes it, ignores it, or contradicts it — and nobody owns reconciling them.**

Concretely, this happened five separate times in your codebase:

| # | Decision | Made by | Re-made / undermined by |
|---|---|---|---|
| 1 | Clean the topic string | LLM (prompt rule 1, 5-shot examples) | `_strip_topic_filler()` regex, run again on the LLM's own output |
| 2 | Pick the platform | LLM (schema field `platform`) | Regex `detected_platform` — LLM's answer is silently discarded |
| 3 | Judge item_kind match | LLM, at generation time (`prompt_composer.py`'s `item_instruction`) | A second, blind LLM call after the fact (`evaluate_item_kind_match`), only wired into `main.py`, not `workflow/graph.py` |
| 4 | Run the generation pipeline | `main.py:run()` (procedural, battle-tested, has real dated bug-fixes) | `workflow/graph.py` (LangGraph, unfinished, un-called, and already behaviorally different — no merge-on-retry, no item_kind gate) |
| 5 | Decide whether an action is destructive | `DESTRUCTIVE_ACTIONS` confirmation gate | Bypassed entirely on the orchestrator's exception path and invalid-tool-call path; `dispatch_action`'s unknown-action fallback defaults straight to `run_new_request` |

Everything below fixes these five, plus the structural cause that let them
happen unnoticed: **every file that talks to Groq or Gemini does so with its
own hand-rolled client, its own JSON-parsing fallback chain, and its own
token-tracking call.** There is no single place that owns "how TrendForge
talks to an LLM," so nobody could see, in one place, how many places were
quietly doing it slightly differently.

---

## 2. Core Design Principles (apply these to every future change)

1. **One decision, one owner.** Before writing a function, name the single
   decision it makes. If another function in the codebase already makes
   that decision, delete one of them — never let both exist "just in case."
2. **Structural checks are code. Semantic checks are prompts.** A missing
   field, a link that doesn't exist in fetched data, a caption over the
   character limit — deterministic, belongs in `gates.py`, no LLM involved.
   "Does this title really name a diet plan" — ambiguous, belongs in a
   prompt with worked examples, not a second blind LLM call.
3. **All LLM calls go through one gateway.** No file imports `Groq` or
   `genai` directly except one module. This is what makes principle 1
   enforceable — you can't have five silent duplicate decisions if there's
   physically one place new LLM calls get added, reviewed, and token-tracked.
4. **Structured output, not prose-then-parse.** Every LLM call that feeds
   the pipeline uses schema-constrained tool-calling. This deletes entire
   fallback-parsing functions rather than making them more robust.
5. **One pipeline implementation.** Not "the graph version and the
   procedural version, pick whichever's imported." One canonical
   implementation, period.
6. **CLI code never gets imported by the web worker, and vice versa.**
   If `api/web/handlers.py` has to `import main` to reach shared logic,
   that logic is in the wrong file.

---

## 3. New Module Map

```
trendforge/
├── core/                      # unchanged — state.py, token_tracker.py
├── config/                    # unchanged
│
├── llm/                       # ★ NEW — the single LLM gateway
│   ├── client.py              #   call_groq(), call_gemini() — the ONLY
│   │                          #   place either SDK is imported
│   ├── schemas.py             #   every structured-output schema, one place
│   └── errors.py              #   LLMCallFailed, LLMSchemaViolation
│
├── understanding/
│   ├── prompt_cleaner.py      # unchanged — rule-based, 0 tokens, owns platform
│   └── intent_extractor.py    # slimmed — no regex re-cleaning, no parsing
│                               #   fallback chain, no discarded platform field
│
├── research/                  # unchanged structurally (fetchers/, routing/)
│
├── generation/
│   ├── content_generator.py
│   ├── prompt_composer.py     # unchanged design — already correctly
│   │                          #   owns the two-axis Strategy Pattern
│   ├── intents/ , platforms/  # unchanged
│   └── formatter.py
│
├── workflow/
│   └── gates.py                # unchanged design — evaluate_fetch_quality,
│                                #   evaluate_post_validation stay code-only.
│                                #   evaluate_item_kind_match stays, now
│                                #   calls llm/client.py instead of its own
│                                #   Groq() instantiation.
│   # workflow/graph.py + nodes.py → DELETED (see §5)
│
├── pipeline/                   # ★ NEW — extracted from main.py
│   └── generate.py             #   run() — the STEP1-5 procedure, fetch-merge
│                                #   retry loop, dual-gate generation retry.
│                                #   Zero print(), zero CLI concerns.
│
├── orchestration/               # ★ NEW — extracted from main.py
│   ├── conversation_agent.py    #   was conversation/orchestrator.py —
│   │                            #   renamed to match agent map in §6
│   └── dispatch.py              #   dispatch_action + all _handle_* +
│                                 #   _snapshot_posts, _summarize_for_chat.
│                                 #   Imports pipeline/generate.py, not main.py.
│                                 #   This is what api/web/handlers.py imports.
│
├── memory/                     # unchanged
├── api/                        # unchanged (app.py, jobs.py, handlers.py,
│                                #   worker.py) — handlers.py now imports
│                                #   orchestration.dispatch, not main
│
└── main.py                     # ★ SHRINKS to ~60 lines — interactive_mode,
                                 #   print_banner, _extract_flags, argparse.
                                 #   Imports orchestration/dispatch.py.
```

---

## 4. The LLM Gateway (`llm/`) — Why This Is the Highest-Leverage Fix

Right now Groq/Gemini clients are instantiated separately in:
`conversation/orchestrator.py` (`process_turn`, `maybe_summarize`),
`understanding/intent_extractor.py`, `workflow/gates.py`
(`evaluate_item_kind_match`), and implicitly in `generation/content_generator.py`.
Each one repeats: client construction, model selection, `temperature`/
`reasoning_effort` params, token extraction from the response, and — in
`intent_extractor.py` — a four-layer manual JSON-repair cascade that exists
*only* because that one call wasn't using structured output the way the
orchestrator's `TOOLS` calls already correctly do.

**Target interface** (design, not final code):

```
llm/client.py
    call_groq(system, user, model, schema=None, tools=None,
              temperature=0.0, reasoning_effort="low") -> LLMResult
    call_gemini(system, user, model, schema=None,
                temperature=0.0) -> LLMResult

LLMResult:
    content: dict | str      # parsed against `schema` if provided — a
                              #   schema violation raises LLMSchemaViolation,
                              #   it does not fall back to regex-guessing
    tokens_used: int
    raw_response: Any        # for debugging only
```

Every call site becomes: pass a schema from `llm/schemas.py`, get back
validated data or a typed exception. Token tracking (`add_tokens`) happens
in **one** place — the gateway — instead of being copy-pasted at every
call site (and occasionally forgotten, which is its own silent bug class).

**What this deletes outright:**
- `_parse_llm_json()`'s entire four-strategy fallback cascade in
  `intent_extractor.py` — structurally impossible to need once the intent
  call uses `response_format`/tool-calling the same way
  `evaluate_item_kind_match` already correctly does today.
- Four separate `from groq import Groq; client = Groq(...)` instantiations.
- Four separate ad-hoc token-extraction lines (`response.usage.total_tokens`,
  `getattr(response.usage, ...)`, etc.) that could each silently drift out
  of sync with each other.

---

## 5. Decision: Delete `workflow/graph.py` + `workflow/nodes.py`

**Verdict: delete, don't finish.** Reasoning:

- `main.py:run()` is the version with real, dated, production bug-fixes
  (fetch-data merge-on-retry, the off-by-one-safe retry counter pattern,
  the P9 CLI-block-leaking-into-chat fix). The graph version doesn't have
  any of these — it's not "a cleaner rewrite," it's an earlier, less
  correct draft that happens to still be in the repo.
- It only implements 1 of your 8 conversation actions
  (`run_new_request`). Finishing it means porting `generate_more`'s
  accumulate-and-renumber logic, `edit_existing`, `undo`,
  `targeted_refetch`, and both constraint handlers — a rewrite, not a cleanup.
- Its own `evaluate_item_kind_match` omission is a live example of exactly
  the "two pipelines silently diverge" risk this whole document exists to
  eliminate. Keeping it around "for later" keeps that risk live.
- Its `ThreadPoolExecutor` 90s timeout would conflict with RQ's own
  `job_timeout=180` the moment it's ever wired into the web path — another
  duplicate-decision bug, currently dormant only because nothing calls it.

If you later want LangGraph specifically for tracing/replay, that's a
legitimate reason to revisit — but as a deliberate rebuild against the
`pipeline/generate.py` version below, not a resurrection of the current file.

---

## 6. Agent Responsibility Map

Treat every LLM call as a named agent with exactly one job. This table is
the canonical reference — if you're about to add a new LLM call, find its
row first; if it doesn't fit a row, that's a sign it's redundant with one
that already exists.

| Agent | Owns | Input | Output (schema-enforced) | Retry-worthy? |
|---|---|---|---|---|
| **PromptCleanerAgent** *(code, not LLM)* | Platform detection, post-count regex, filler stripping | raw text | `detected_platform`, `detected_post_count`, `cleaned_text` | n/a |
| **IntentAgent** | topic, category, content_intent, item_kind, search queries | cleaned text + rule pre-extraction | `IntentSchema` | No — get it right via prompt examples, not retries |
| **RouterAgent** | which sources to fetch from | category, topic | `selected_sources` | No — deterministic rule table first, LLM fallback only |
| **FetchQualityGate** *(code, not LLM)* | is fetched data sufficient | `fetched_data`, `sources_used` | `sufficient`, `should_retry`, `next_query` | n/a — drives retry of fetchers, not itself |
| **GenerationAgent** | the actual post content | topic, fetched data, intent+platform strategy guidance | `GeneratedPostsSchema` | Yes — capped retries on gate failure |
| **PostValidationGate** *(code, not LLM)* | structural correctness (fields, links real, length, dupes) | `generated_posts` | `valid`, `errors` | n/a |
| **ItemKindGate** *(LLM, lightweight)* | does each title really name the requested item_kind | `item_kind`, titles only | `mismatched_indices` | Yes, shares generation retry budget |
| **ConversationAgent** | which of 8 actions this turn maps to | message history, current posts, constraints | one `TOOLS` call | No — `clarify` is the retry mechanism, not a second guess |
| **SummarizerAgent** | compress overflowing history | old turns | `rolling_summary` | No |

Note what's *not* an agent: **destructive-action confirmation.** That's not
a decision an LLM makes at all — it's a code-level circuit breaker that
wraps the ConversationAgent's output. See §8.

---

## 7. File-by-File Migration Table

| Current | Action | Reasoning |
|---|---|---|
| `understanding/intent_extractor.py` → `_strip_topic_filler`, `TOPIC_FILLER_PATTERN`, `TRAILING_WORD_PATTERN` | **Delete** | Redundant with LLM rule 1; actively eats legitimate topic words ("Top Gun," "Best practices") |
| `understanding/intent_extractor.py` → `platform` field in `INTENT_SYSTEM_PROMPT` schema | **Delete from schema** | Answer is already discarded by `_merge_into_state`; wastes model attention that should go to `item_kind` |
| `understanding/intent_extractor.py` → `_parse_llm_json` (4-layer fallback) | **Delete**, replaced by `llm/client.py` structured output | See §4 |
| `workflow/gates.py` → `evaluate_item_kind_match` | **Keep**, but repoint its `Groq(...)` call through `llm/client.py` | Legitimate lightweight semantic gate; just needs to stop hand-rolling its client |
| `workflow/graph.py`, `workflow/nodes.py` | **Delete** | See §5 |
| `main.py` → `run()` | **Move** to `pipeline/generate.py`, strip all `print()` | CLI-only concern currently fused into shared logic |
| `main.py` → `dispatch_action`, all `_handle_*`, `_snapshot_posts`, `_summarize_for_chat`, `_EDIT_ERROR_MESSAGES` | **Move** to `orchestration/dispatch.py` | This is what `api/web/handlers.py` actually needs; today it drags in the entire CLI module to get it |
| `main.py` → `interactive_mode`, `print_banner`, `_extract_flags`, `main()`/argparse | **Stays** in `main.py` | Genuinely CLI-only; file shrinks to ~60 lines |
| `conversation/orchestrator.py` | **Rename** → `orchestration/conversation_agent.py`; repoint Groq calls through `llm/client.py` | Matches the agent map naming; no behavior change needed beyond the fix in §8 |
| `api/web/handlers.py` → `import main` | **Change** to `import orchestration.dispatch as dispatch` | Removes the CLI-into-worker coupling entirely |

---

## 8. The One Behavior Change That Isn't Optional

Two independent bypasses of the destructive-confirmation gate exist today,
both defaulting to **replace-without-asking**:

1. `orchestrator.py`'s `process_turn` — the invalid-tool-call branch and the
   top-level `except Exception` branch both `return fallback` (which *is*
   `run_new_request`) without ever routing through `DESTRUCTIVE_ACTIONS`.
2. `main.py`'s `dispatch_action` — an unrecognized `action` string falls
   back to `handlers["run_new_request"]` directly.

**Fix pattern:** move the destructive-confirmation check to wrap the
*final resolved action*, after every fallback and error path, not just
the clean-parse happy path. Concretely: every `return` in `process_turn`
that could resolve to `run_new_request` — success, malformed-args,
exception — passes through one shared "is this destructive and are
there posts to lose" check before it leaves the function, no exceptions.
Same principle in `dispatch_action`'s unknown-action branch: default to
`clarify`, never straight to `run_new_request`.

This is the single highest-priority fix in this document — it's the one
item that's an active safety gap today, not just a maintainability risk.

---

## 9. Prompt Standards Going Forward

- **Delete "Return ONLY valid JSON, nothing else" boilerplate** once a
  call uses `llm/client.py`'s `schema=` — the schema enforces this
  structurally, the sentence is now dead weight competing for the model's
  attention with real instructions.
- **One example set per ambiguous rule, not one example set for the whole
  prompt.** `intent_extractor.py`'s item_kind rule 5 needs 2-3 more
  examples targeting the genuinely ambiguous middle ("5 productivity
  tips" — discrete or topic-decomposition?) with the disambiguating rule
  stated explicitly ("if each item needs its own proper name/title, it's
  discrete").
- **Every field in a JSON schema must have exactly one consumer.** Before
  adding a field to any schema, name the line of code that reads it. If
  you can't, don't add the field (this is what caught the discarded
  `platform` field).
- **Retries fix structural errors, not semantic ones.** `prompt_composer.py`'s
  `correction_block` (retry_count > 0) is correctly used today for things
  like "caption too long" — keep that. Don't extend the same retry
  mechanism to try to fix "the model misunderstood item_kind" — that's a
  prompt-example problem, not a retry problem (see item above).

---

## 10. Suggested Rollout Order

1. **Ship the confirmation-gate fix (§8) first, alone.** It's the one live
   safety issue; everything else is maintainability.
2. **Build `llm/client.py` + `llm/schemas.py`**, migrate one call site
   (`intent_extractor.py`) to prove the pattern, delete `_parse_llm_json`
   and the regex-cleaning functions.
3. **Migrate the remaining call sites** (orchestrator, item_kind gate,
   summarizer) to the gateway.
4. **Delete `workflow/graph.py` + `nodes.py`.**
5. **Split `main.py`** into `pipeline/generate.py` + `orchestration/dispatch.py`
   + slimmed `main.py`; repoint `api/web/handlers.py`'s import.

Each step is independently shippable and testable — you don't need to do
this as one large rewrite.