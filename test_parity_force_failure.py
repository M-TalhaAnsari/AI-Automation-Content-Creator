# test_parity_forced_failure.py — throwaway script, delete after
#
# Forces the router stage to raise an exception in BOTH paths, to confirm
# main.py::run()'s try/except graceful-degradation and workflow/graph.py's
# node_route() mirror of it actually behave the same way when something
# really does fail — not just when everything happens to succeed.

import sys
import types

prompt = "top 5 machine learning projects for instagram"


def break_router():
    """Injects a fake routing.router_orchestrator module whose
    RouterOrchestrator.route() always raises. Both main.py and
    workflow/nodes.py import RouterOrchestrator lazily inside their
    try blocks, so patching sys.modules before each call forces the
    same failure in both paths."""
    fake_module = types.ModuleType("routing.router_orchestrator")

    class BrokenRouterOrchestrator:
        def route(self, state):
            raise RuntimeError("SIMULATED ROUTER FAILURE (test_parity_forced_failure.py)")

    fake_module.RouterOrchestrator = BrokenRouterOrchestrator
    sys.modules["routing.router_orchestrator"] = fake_module


def restore_router():
    if "routing.router_orchestrator" in sys.modules:
        del sys.modules["routing.router_orchestrator"]


print("=== Forcing router stage to fail for OLD path ===")
break_router()
from main import run
old = run(prompt)
restore_router()

print("\n=== Forcing router stage to fail for NEW path ===")
break_router()
from workflow.graph import run_graph
new = run_graph(prompt)
restore_router()

print("\n=== Results ===")
print(f"OLD posts generated despite router failure: {len(old.get('posts', []))}")
print(f"NEW posts generated despite router failure: {len(new.get('posts', []))}")
print(f"OLD errors: {old.get('errors')}")
print(f"NEW errors: {new.get('errors')}")

assert len(old.get("posts", [])) > 0, "OLD path did NOT degrade gracefully — no posts produced after router failure"
assert len(new.get("posts", [])) > 0, "NEW path did NOT degrade gracefully — no posts produced after router failure"
assert old.get("errors") == new.get("errors"), (
    f"Error lists diverged between paths — OLD={old.get('errors')!r} NEW={new.get('errors')!r}"
)

print("\n✅ Both paths survived the forced router failure and still produced output.")\






