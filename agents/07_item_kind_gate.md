# Agent 7 — ItemKindGate

**Core question this agent answers:**
*"Does each generated title genuinely name a specific instance of the
requested item_kind, or is it a related-but-different concept?"*

- **Type:** LLM (Groq small, cheap — titles only, no full post content in
  the prompt). Structured output.
- **LangGraph node:** Part of the combined `evaluate_generation` node
  (see `00_graph_wiring.md`, Fix 1) — this is the fix: the old
  `workflow/graph.py` never called this at all; only `main.py`'s
  procedural loop did.
- **File:** `workflow/gates.py::evaluate_item_kind_match`.
- **Calls through:** `llm/client.py::call_groq(schema=ItemKindCheckSchema)`
  — replaces this function's own inline `Groq(...)` instantiation.

## Inputs
- `item_kind` (from Agent 2 — skip entirely if empty)
- `[post.title for post in generated_posts]`

## Output schema — `ItemKindCheckSchema`
```
{ "mismatched_indices": list[int], "reason": str }
```

## System prompt (unchanged — already well-scoped)
```
You check whether generated titles match a requested category. For each
title, decide whether it genuinely names a specific instance of
"{item_kind}" (not a related practice, technique, or adjacent concept).
```

## Why this agent exists as a *separate* call rather than folded into
## GenerationAgent
Two reasons, both intentional:
1. **Cheap and fast** — titles only, no full post bodies, no fetched
   data in context. Running it as its own call keeps the expensive
   generation call's context focused purely on content quality.
2. **A second, independent check is legitimate here specifically because
   it's checking a narrow, well-defined semantic property (does this
   noun phrase name an instance of X) against a small, fixed input (a
   list of titles) — not re-deciding a broad, ambiguous judgment call
   with less context than the original.** This is different from the
   deleted regex topic-cleaning duplication: that was blindly re-doing
   the *same* decision with *worse* information. This is a narrow,
   additional check with a *smaller*, well-scoped decision space.

## Must NOT do
- Must not receive full post content (captions, hooks, hashtags) — if
  it needs more than the title to judge item_kind, that's a sign
  Agent 2's `item_kind` definition itself is ambiguous and needs better
  examples (see Agent 2's rule 5), not a reason to expand this agent's
  input.
- If this gate is triggering retries often for a given item_kind
  pattern, that is a signal to strengthen Agent 2's prompt examples for
  that pattern — not a signal to add a third gate.

## Downstream consumer
`node_evaluate_generation` combines `mismatched_indices` (converted to
error strings) with Agent 6's errors into the single retry decision.
