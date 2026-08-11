# Agent 9 — SummarizerAgent

**Core question this agent answers:**
*"Now that conversation history has overflowed the sliding window, what's
the minimum summary that preserves topic changes, standing preferences,
and what's already been generated?"*

- **Type:** LLM (Groq small, low reasoning effort — this is a cheap,
  low-stakes compression task, not a judgment call).
- **LangGraph node:** No — runs after each turn completes, independent of
  the generation graph. Called from `orchestration/dispatch.py` (was
  `maybe_summarize`, unchanged location/logic — `orchestration/conversation_agent.py`).
- **Calls through:** `llm/client.py::call_groq(...)` (no schema needed —
  free-text summary is the correct output shape here, not everything
  needs structured output).

## Inputs
- `overflow` — turns pushed out of the `SLIDING_WINDOW_TURNS` (20) window
- `rolling_summary` — the prior summary, if one exists, folded in as
  context rather than discarded

## Output
- `rolling_summary: str` (2-4 sentences)

## System prompt (unchanged — already well-scoped)
```
Summarize this conversation segment in 2-4 sentences. Focus on topic
changes, standing preferences, and what content was generated.
```

## Must NOT do
- Must not be asked to summarize and also extract structured fields
  (e.g. "and list any constraints mentioned") — if constraint-tracking
  needs fixing, that's `add_constraint`/`remove_constraint`'s job at the
  time they're stated, not a second extraction pass here. This agent's
  only output is the free-text rolling summary.
- Must not run on every turn — only when `message_history` exceeds
  `SLIDING_WINDOW_TURNS`. Running it unconditionally would silently
  double token spend on every short conversation for no benefit.

## Downstream consumer
`ConversationAgent` (Agent 8) reads `rolling_summary` and includes it in
the system prompt for every subsequent turn.
