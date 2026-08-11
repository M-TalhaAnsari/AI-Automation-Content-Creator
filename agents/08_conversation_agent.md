# Agent 8 — ConversationAgent

**Core question this agent answers:**
*"Given this chat message and what's already been generated, which one
of the 8 actions should run — and is it safe to run without confirming
first?"*

- **Type:** LLM (Groq large), native tool-calling — `tool_choice="auto"`
  over the fixed `TOOLS` schema. This part is already correctly designed;
  do not change the tool-calling mechanism itself.
- **LangGraph node:** **No.** This operates one layer above the
  generation graph — it decides *whether* to invoke the graph at all
  (for `run_new_request`/`generate_more`) or dispatch a direct action.
  It is called once per user turn from `orchestration/dispatch.py`,
  before the graph is ever touched.
- **File:** `orchestration/conversation_agent.py` (renamed from
  `conversation/orchestrator.py` — see migration table).
- **Calls through:** `llm/client.py::call_groq(tools=TOOLS)`.

## Inputs
- `message_history` (sliding window, last 20 turns)
- `rolling_summary` (from Agent 9, if history overflowed)
- `last_generated_posts` (titles only, numbered)
- `active_constraints`
- `pending_confirmation` (if the previous turn asked for one)

## Output
- One of the 8 tool calls (`run_new_request`, `generate_more`,
  `edit_existing`, `add_constraint`, `remove_constraint`,
  `targeted_refetch`, `undo`, `clarify`) + its arguments.

## The confirmation circuit breaker — code, not this agent's judgment
`DESTRUCTIVE_ACTIONS = {"run_new_request"}` triggers a mandatory
confirmation turn whenever `last_generated_posts` is non-empty. This is
**not** a decision `ConversationAgent` makes — it's a code-level wrapper
around whatever this agent decides. Concretely:

**Every return path** — clean tool-call, malformed tool-call args, and
the top-level exception handler — must pass through the same
"is the resolved action destructive and are there posts to lose" check
before leaving the function. Previously, the malformed-args and
exception paths both skipped straight to the `run_new_request` fallback,
bypassing confirmation entirely. This was the one live safety bug found
in the audit — see `TrendForge_Architecture_Redesign.md` §8. Fixed here:
no return statement in this file is allowed to resolve to
`run_new_request` without going through the shared confirmation check
first, including the fallback and error paths.

## Must NOT do
- Must not re-derive `platform`, `core_topic`, or `item_kind` — those
  belong entirely to Agent 2. This agent only decides *which action*, not
  *what the content should be*. If you find yourself wanting this agent
  to reason about topic quality, that reasoning belongs in Agent 2 or 5,
  not here.
- On a pending confirmation, must not be trusted to re-derive *what*
  action to run — only whether the user affirmed or declined. The
  originally stored `pending["action"]`/`pending["args"]` execute
  deterministically; this agent's confirmation-turn output is binary
  (proceed / clarify), never a fresh action.

## Downstream consumer
`orchestration/dispatch.py::dispatch_action` reads the resolved
`{action, args}` and either calls the LangGraph engine
(`run_new_request`, `generate_more`) or a direct handler (everything else).
