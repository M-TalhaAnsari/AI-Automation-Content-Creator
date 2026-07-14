# test_parity_forced_failure.py — throwaway script, delete after
#
# v2 — fixes two problems found in the first version's actual run:
#
# 1. The original script asserted exact string equality on live Gemini
#    429 error messages. Those messages contain a non-deterministic
#    retryDelay value that will never match between two separate live
#    API calls, even when both paths hit the identical error condition.
#    That was a bug in THIS TEST, not in main.py or workflow/graph.py —
#    fixed below by comparing error category instead of exact text.
#
# 2. The original script never actually proved the router exception
#    fired on the NEW path — run_graph() prints nothing, so "it didn't
#    crash and produced posts" was the only thing verified, not "the
#    forced failure was genuinely exercised the same way on both sides."
#    Fixed below with a call-counter on the fake broken router, and by
#    bypassing run_graph()'s 9-key wrapper to inspect the NEW path's
#    full raw state (selected_sources, errors) for a real comparison.

import sys
import types
import uuid

router_call_log = []

prompt = "top 5 machine learning projects for instagram"


def break_router():
    """Injects a fake routing.router_orchestrator module whose
    RouterOrchestrator.route() always raises, and records that it was
    actually called — so this test can prove the exception fired,
    not just assume it did."""
    fake_module = types.ModuleType("routing.router_orchestrator")

    class BrokenRouterOrchestrator:
        def route(self, state):
            router_call_log.append("called")
            raise RuntimeError("SIMULATED ROUTER FAILURE (test_parity_forced_failure.py)")

    fake_module.RouterOrchestrator = BrokenRouterOrchestrator
    sys.modules["routing.router_orchestrator"] = fake_module


def restore_router():
    if "routing.router_orchestrator" in sys.modules:
        del sys.modules["routing.router_orchestrator"]


def error_category(err_list):
    """Groups error messages by category instead of exact text — a live
    API error's retryDelay/timestamp fields will never match byte-for-byte
    across two separate calls, even for the identical underlying error."""
    cats = set()
    for e in err_list:
        if "RESOURCE_EXHAUSTED" in e:
            cats.add("GEMINI_429_QUOTA")
        else:
            cats.add(e[:40])
    return sorted(cats)


# ── OLD path ──────────────────────────────────────────────────────
print("=== OLD path (main.py::run) ===")
router_call_log.clear()
break_router()
from main import run
old = run(prompt)
restore_router()
old_router_calls = len(router_call_log)

# ── NEW path — bypass run_graph()'s 9-key wrapper for full state visibility ──
print("\n=== NEW path (raw compiled graph, full state inspected — not just the public run_graph() contract) ===")
router_call_log.clear()
break_router()
from core.state import create_initial_state
from workflow.graph import _compiled_graph
new_state = create_initial_state(raw_prompt=prompt, session_id=str(uuid.uuid4())[:8])

# Using .stream() instead of .invoke() here — run_graph()'s .invoke() call
# is completely silent while running, which is easy to mistake for a hang
# during a slow run (Gemini 429 + retry + Groq fallback can take 60-120s+,
# as the OLD path above just demonstrated). .stream() surfaces which node
# is currently executing, so "still working" is visibly distinguishable
# from "actually stuck." This is a test-only diagnostic technique — it
# doesn't require changing graph.py or nodes.py at all.
final_state = new_state
for update in _compiled_graph.stream(new_state, stream_mode="updates"):
    node_name = next(iter(update))
    print(f"  [Graph] node '{node_name}' completed")
    final_state = update[node_name]
new_state = final_state

restore_router()
new_router_calls = len(router_call_log)

# ── Prove the forced failure actually fired on both sides ─────────
print(f"\nRouter exception fired — OLD: {old_router_calls} time(s) | NEW: {new_router_calls} time(s)")
assert old_router_calls == 1, "OLD path's router exception never fired — test setup broken"
assert new_router_calls >= 1, "NEW path's router exception never fired — patch didn't take, or import caching bypassed it"
if new_router_calls > 1:
    print(f"  (NEW path retried fetch {new_router_calls - 1} extra time(s) — expected now that the "
          f"fetch-quality gate's link-quality check can trigger a route/fetch retry. Each retry hits "
          f"the same mocked-broken router, so this is the gate correctly detecting persistently poor "
          f"data, not a bug in the retry count itself.)")

# ── Compare actual behavior, not just "did it crash" ───────────────
print(f"OLD posts: {len(old.get('posts', []))}")
print(f"NEW posts: {len(new_state.get('generated_posts', []))}")
print(f"NEW session_id (open output/session_{{this}}.txt to inspect the actual final links): {new_state.get('session_id')}")
assert len(old.get("posts", [])) > 0, "OLD path did not degrade gracefully — no posts produced"
assert len(new_state.get("generated_posts", [])) > 0, "NEW path did not degrade gracefully — no posts produced"

print(f"NEW selected_sources after router failure: {new_state.get('selected_sources')}")
assert new_state.get("selected_sources") == ["google_trends", "hackernews"], (
    f"NEW path's fallback sources differ from the expected default — got {new_state.get('selected_sources')}"
)

old_cat = error_category(old.get("errors", []))
new_cat = error_category(new_state.get("errors", []))
print(f"OLD error categories: {old_cat}")
print(f"NEW error categories: {new_cat}")
assert old_cat == new_cat, f"Error CATEGORIES diverged — OLD={old_cat} NEW={new_cat}"

print("\n✅ Router exception confirmed fired on both paths, same fallback sources used, same error category, both produced output.")