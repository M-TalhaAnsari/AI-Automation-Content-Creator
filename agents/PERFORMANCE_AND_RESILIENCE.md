# TrendForge — Performance & Resilience

> Companion to `ARCHITECTURE.md`. That document is organized by file;
> this one is organized by two cross-cutting concerns that don't belong
> to any single file: **making the pipeline faster through real
> concurrency**, and **handling new bugs/errors without the function
> count growing without bound**. Read `ARCHITECTURE.md` §0 first — the
> same "ask before assuming" rule applies here.

---

## Part 1 — Concurrency

Each item below states what's safe to parallelize, why, and — just as
important — what was considered and rejected, so a future pass doesn't
re-propose something already ruled out for a documented reason.

### 1.1 Fetch fan-out — do this
`selected_sources` are independent HTTP calls to unrelated APIs. Fan
them out (thread pool or `asyncio.gather`) in
`fetcher_orchestrator.py`. Stagger or rate-limit GitHub specifically —
its burst limit is tighter than its hourly quota.

### 1.2 Route concurrently with Intent — do this, conditional payoff
Today: `intent` (LLM) → `route` (needs `detected_category` from
`intent`'s output) → `fetch`. Fix: move category detection into
`prompt_cleaner.py` as a deterministic keyword classifier against the
fixed category enum (tech/business/lifestyle/education/entertainment/
news) — the same kind of classification that file already does for
platform. `RuleRouter` then reads the rule-based category and can start
the moment `prompt_clean` finishes, running **concurrently** with
`intent`'s LLM call for topic/item_kind/search_queries. `fetch` waits
for both to finish (it needs `selected_sources` from route and
`search_queries` from intent either way).

Honest caveat: when the rule-based category is ambiguous,
`RuleRouter.can_handle()` still returns False and falls to
`LLMRouter`, which needs `core_topic` — so in that branch you're back
to waiting on `intent` anyway. Net effect: a real win on the common
case, no regression on the ambiguous case.

### 1.3 Merge SelectionAgent into GenerationAgent — do this
See `agents/05_generation_agent.md` and `agents/10_selection_agent.md`
for the full reasoning. One fewer full LLM round trip per generation,
implemented as a prompt-instruction addition plus deleting the Pass-1
call and regroup step — not a new module.

### 1.4 Conditional ItemKindGate — optional, your call
For `generate_more` only: skip the verifier on the first attempt,
invoke it only if `PostValidationGate` already forced a retry for an
unrelated reason. Real quality/speed tradeoff — don't apply silently,
decide deliberately. Keep `run_new_request` always-verified; it's the
higher-stakes, first-impression call.

### 1.5 Defer `maybe_summarize` — do this
It's background bookkeeping for future turns — nothing about the
current reply depends on it. Move it out of the synchronous
request/reply path (fire-and-forget after the reply is sent, or a
cheap deferred job) instead of making the user wait on an unrelated
summarization call.

### 1.6 Race Gemini and Groq instead of fallback-after-failure — optional, real cost tradeoff
Cuts tail latency (take whichever returns first) but means paying for
both calls on *every* generation, not just failures. Worth it only if
you're specifically optimizing p99 latency and accept the doubled
cost. Not a default recommendation — flagging as an available lever,
not a fix.

### 1.7 Rejected — speculative generation during a fetch retry
Considered: start drafting on the first fetch attempt's data while
`FetchQualityGate` is still deciding whether a retry is needed, discard
if it retries. Rejected: fetch retries are capped at 2 and meant to be
rare. The expected cost of throwing away a wasted generation call
outweighs the latency saved in the common no-retry case. Don't
re-propose this without new evidence retries are happening far more
often than the 2-retry cap implies they should.

### 1.8 Sequential by design — do not parallelize
`prompt_clean → intent → route → fetch → generate` has genuine data
dependencies at every arrow (route needs category, generate needs
validated data). The retry loops (`evaluate_fetch → route`,
`evaluate_generation → generate`) are inherently sequential — that's
what "retry until satisfied" means. Parallelizing across these isn't a
speed win, it's a correctness bug.

---

## Part 2 — Handling New Bugs Without Unbounded Function Growth

This is the direct answer to "we don't want to write a new function for
every bug." The honest version of that answer isn't "you'll never write
another function" — new deterministic facts about the world will always
warrant new checks. The actual fix is that **the system should never
need surgery to add one**, and most failure categories shouldn't
produce a new function at all. Four categories, four different
mechanisms:

### 2.1 Deterministic invariants → a registry, not a new branch
Every gate function (`workflow/gates.py`) already returns the same
shape: `{valid, errors, should_retry}`. Formalize this contract as a
registry:
```
GATE_REGISTRY = [evaluate_post_validation, evaluate_item_kind_match]

def run_gates(state):
    results = [g(state) for g in GATE_REGISTRY]
    return {
        "valid": all(r["valid"] for r in results),
        "errors": [e for r in results for e in r["errors"]],
        "should_retry": any(r["should_retry"] for r in results),
    }
```
Adding gate #3 for a newly-discovered structural invariant (a new kind
of ground-truth fact worth checking) means appending one line to
`GATE_REGISTRY` — `node_evaluate_generation` never changes. This is
also how `evaluate_fetch_quality` should be organized if it ever grows
a second check.

### 2.2 Semantic misjudgments → prompt examples + a regression set, not a new gate
This is the pattern already used correctly for `item_kind` rule 5.
When a real production failure is a *judgment* problem (wrong tone,
wrong category boundary, subtle misread of intent) — not a fact you can
check against ground truth — the fix is:
1. Add the specific failure case as a worked example to the relevant
   prompt (see `agents/02_intent_agent.md`'s rule 5 for the pattern).
2. Add the same case to a running regression file — input, expected
   output — and replay the full regression set before shipping any
   change to that prompt.

This is data growing, not code growing. It's the mechanism that
prevents the function-per-bug spiral specifically for the failure
category that would otherwise cause it — judgment calls don't have a
deterministic fix, so the fix has to be "teach the model," and teaching
needs to be checked, hence the regression set.

### 2.3 Transient/systemic failures → one centralized retry policy in `llm/client.py`
Rate limits, timeouts, provider outages — these get one retry/backoff
policy, defined once in the gateway (§2 of `ARCHITECTURE.md`), not a
try/except per call site. A new *shape* of transient failure (say, a
provider changes its rate-limit error format) gets fixed once, in the
gateway, and every caller inherits the fix automatically. This is the
other reason `llm/client.py` matters beyond de-duplicating boilerplate.

### 2.4 Explicitly rejected: a generic LLM-based "error recovery agent"
Tempting pattern: one meta-agent that looks at any failure — of any
kind, from any source — and decides how to recover, replacing 2.1–2.3
above with a single adaptive decision-maker. **Don't build this.**
Recovery from a destructive-action failure, or a malformed schema
response, needs to behave identically every time the same failure
occurs. An LLM's recovery decision can vary run to run for the same
input — that's the exact unreliability this whole redesign has been
removing from the happy path, relocated to the error path instead of
actually solved. Systemic recovery is a policy decision (fixed retry
count, fixed fallback behavior), the same category as the destructive-
action confirmation gate — not a judgment call, and not something to
hand to a model's discretion.

### 2.5 What this means in practice, next time a bug shows up
Before writing anything, classify the bug:
- **"The output contains a fact that's checkably wrong"** → §2.1, add
  to the gate registry.
- **"The output is technically valid but not what was meant"** → §2.2,
  add a prompt example + regression case.
- **"The call failed for an infrastructure reason"** → §2.3, check
  whether the gateway's existing retry policy already covers it before
  writing anything new.
- **"I'm not sure which of these it is"** → it's very likely §2.2.
  Structural and infrastructure failures are usually obvious from the
  error itself; judgment-call failures are the ambiguous-feeling ones.
