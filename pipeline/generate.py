"""
pipeline/generate.py — Core generation pipeline entry point

FIX: now the thin wrapper around workflow/graph.py::run_graph() that
FLOW.md's migration plan called for, instead of a second, hand-rolled
copy of the fetch/retry/generate/retry loop. The graph already encodes
that exact retry-until-satisfied logic as LangGraph conditional edges
(see workflow/graph.py), and it now reads a correct, cumulative item
count (workflow/gates.py's evaluate_fetch_quality fix) — so there is no
remaining reason for this file to duplicate that logic instead of
calling it.

run_graph()'s return dict is byte-for-byte the same 9 keys this
function returns (output, session_id, tokens, total_tokens, errors,
posts, topic, platform, content_intent) — see workflow/graph.py's own
docstring, "Same 9-key return contract as main.py::run()". That's why
this function can just call it and return the result directly.

What this trades away, flagged explicitly rather than silently lost:

1. LIVE STEP PROGRESS. The old run() printed "[1/5] Understanding
   prompt... ✅ topic=...", "[2/5] Selecting sources...", etc. as each
   stage finished. The graph's nodes log the equivalent detail via
   add_log(state, ...) (workflow/nodes.py), but run_graph()'s return
   contract doesn't expose state["logs"] at all, so none of that is
   visible during or after a run through this wrapper. What you get
   instead: a header before the graph runs, and the final output block
   + any errors after it returns.

2. VERBOSE LOG DUMP. The old run(verbose=True) printed every entry in
   state["logs"] at the end. Same root cause as #1 — run_graph() doesn't
   return logs, so `verbose` is still accepted here (for call-site
   compatibility with orchestration/dispatch.py, which passes it
   through unconditionally) but currently has nothing to act on.

3. SAVED-PATH MESSAGE. node_format calls save_output(state) for its
   side effect only and deliberately does NOT store the returned path on
   state (see workflow/nodes.py::node_format's docstring — "avoids
   adding an undocumented field to the schema for something the
   contract never exposed anyway"). So "💾 Saved to: ..." can't be
   reconstructed here either.

None of these are silently decided — extending run_graph()'s return
contract to carry logs/saved_path is a workflow/graph.py change (a
different, already-documented-as-fixed interface) and a separate call
than this file's own split, so it isn't made here. If you want the
progress UX back, that's the next concrete decision: extend
run_graph()'s return dict, or accept this as the graph migration's
known UX tradeoff.

ALSO UNRESOLVED, carried forward from workflow/graph.py's own docstring:
this wrapper is exactly the path that makes the CLI-timeout observation
in run_graph() concrete rather than hypothetical. Before this change,
main.py's CLI path never called run_graph() at all (see the prior
session's diff-verified relocation) — now, via
orchestration/dispatch.py -> pipeline.generate.run -> run_graph(), it
does, with zero timeout protection on that path if a node hangs. Still
not decided here, per run_graph()'s own instruction not to guess at
this — see that file's docstring for the two concrete options.
"""

from workflow.graph import run_graph


def run(prompt: str, platform: str = None, post_count: int = 5, verbose: bool = False) -> dict:
    print(f"\n  ┌─ Prompt:  \"{prompt[:72]}{'...' if len(prompt) > 72 else ''}\"")
    print(f"  └─ Platform: {platform or '(default)'} | Posts: {post_count}\n")

    result = run_graph(prompt, platform=platform, post_count=post_count)

    print(result["output"])
    if result["errors"]:
        print("\n  ⚠️  Warnings:")
        for e in result["errors"]:
            print(f"     • {e}")

    return result