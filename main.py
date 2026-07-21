"""
main.py — TrendForge Interactive Runner
(patched: see FIX comments for exactly what changed and why)
"""

import sys, os, uuid, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG, SUPPORTED_PLATFORMS
from core.state import create_initial_state, get_total_tokens, add_log, add_tokens

MAX_ACTIVE_CONSTRAINTS = 20
MAX_RECENT_MESSAGES = 5


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║         TRENDFORGE v1.0 — Trend Intelligence         ║
║   Real data. Any topic. Platform-ready content.      ║
╚══════════════════════════════════════════════════════╝""")


def run(prompt: str, platform: str = None, post_count: int = 5, verbose: bool = False) -> dict:
    session_id = str(uuid.uuid4())[:8]
    state = create_initial_state(raw_prompt=prompt, session_id=session_id)
    if platform and platform in SUPPORTED_PLATFORMS:
        state["platform"] = platform
    if post_count:
        state["post_count"] = post_count

    print(f"\n  ┌─ Session: {session_id}")
    print(f"  │  Prompt:  \"{prompt[:72]}{'...' if len(prompt)>72 else ''}\"")
    print(f"  └─ Platform: {state['platform']} | Posts: {state['post_count']}\n")

    print("  [1/5] 🧠 Understanding prompt...")
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
        print(f"        ✅ topic='{state['core_topic']}' | platform={state['platform']} | "
              f"category={state['detected_category']} | tokens={state['tokens']['prompt_parsing']}")
    except Exception as e:
        print(f"        ⚠️  Parser error: {e} — using raw prompt")
        state["core_topic"] = prompt[:60]

    print("  [2/5] 🔀 Selecting sources...")
    try:
        from routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
        print(f"        ✅ sources={state['selected_sources']} | method={state['routing_method']}")
    except Exception as e:
        print(f"        ⚠️  Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]

    print("  [3/5] 🌐 Fetching live data...")
    try:
        from fetchers.fetcher_orchestrator import FetcherOrchestrator
        state = FetcherOrchestrator().fetch(state)
        print(f"        ✅ {state['total_items_fetched']} items from {state['sources_used']}")
    except Exception as e:
        state["fetched_data"], state["total_items_fetched"], state["sources_used"] = {}, 0, []
        print(f"        ⚠️  Fetch error: {e} — continuing without live data")

    try:
        from memory.session_store import get_already_covered
        state["already_covered"] = get_already_covered(state["core_topic"], state["platform"])
    except Exception as e:
        state["already_covered"] = []
        add_log(state, f"[Main] Already-covered lookup skipped: {e}")

    print("  [4/5] ✨ Generating content...")
    try:
        from generation.content_generator import ContentGenerator
        state = ContentGenerator().generate(state)
        print(f"        ✅ {len(state['generated_posts'])} posts | tokens={state['tokens']['content_generation']}")
    except Exception as e:
        print(f"        ❌ Generation failed: {e}")
        state["generated_posts"] = []

    print("  [5/5] 📦 Formatting output...\n")
    from generation.formatter import format_output, save_output
    state = format_output(state)
    saved_path = save_output(state)

    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        add_log(state, f"[Main] Session history save failed: {e}")

    print(state["final_output"])
    if saved_path:
        print(f"\n  💾 Saved to: {saved_path}")
    if verbose and state.get("logs"):
        print("\n  📋 LOGS:")
        for log in state["logs"]:
            print(f"     {log}")
    if state["errors"]:
        print("\n  ⚠️  Warnings:")
        for e in state["errors"]:
            print(f"     • {e}")

    return {
        "output": state["final_output"], "session_id": session_id,
        "tokens": state["tokens"], "total_tokens": get_total_tokens(state),
        "errors": state["errors"], "posts": state["generated_posts"],
        "topic": state.get("core_topic", ""), "platform": state.get("platform", ""),
        "content_intent": state.get("content_intent", ""),
    }


def _extract_flags(prompt: str):
    platform, posts = None, 5
    m = re.search(r'--platform\s+(\S+)', prompt)
    if m and m.group(1) in SUPPORTED_PLATFORMS:
        platform = m.group(1)
        prompt = prompt.replace(m.group(0), '').strip()
    m = re.search(r'--posts\s+(\d+)', prompt)
    if m:
        posts = int(m.group(1))
        prompt = prompt.replace(m.group(0), '').strip()
    return prompt.strip(), platform, posts


def _handle_run_new_request(args, prompt, platform, posts, verbose, conversation):
    # FIX: this previously ignored `args` entirely and always used the
    # raw closure `prompt`/`platform` -- meaning the orchestrator's
    # resolved, context-aware instruction (which correctly folds in the
    # conversation history) was thrown away, and the pipeline ran on
    # whatever the user literally typed this turn instead. This is the
    # bug that produced the n8n/LangChain mismatch in the logs: the
    # orchestrator wrote the right prompt, it just never got used.
    resolved_prompt = args.get("prompt") or prompt
    resolved_platform = args.get("platform") or platform
    if verbose and resolved_prompt != prompt:
        print(f"  [Action] using orchestrator-resolved prompt instead of raw input:\n"
              f"           {resolved_prompt!r}")
    result = run(resolved_prompt, platform=resolved_platform, post_count=posts, verbose=verbose)
    conversation["last_topic"] = result.get("topic")
    conversation["last_platform"] = result.get("platform")
    conversation["last_content_intent"] = result.get("content_intent")
    conversation["last_generated_posts"] = result.get("posts", [])
    conversation["last_output"] = result.get("output")


def _handle_edit_existing(args, conversation, verbose):
    from conversation.actions import edit_existing
    from generation.formatter import format_output, save_output
    target_posts, instruction = args.get("target_posts", "all"), args.get("instruction", "")
    if verbose:
        print(f"  [Action] edit_existing(target_posts={target_posts!r}, instruction={instruction!r})")
    result = edit_existing(target_posts, instruction, conversation.get("last_generated_posts", []))

    # FIX: edit_existing can now report a real failure via result["error"]
    # instead of silently returning the same posts unchanged with no
    # signal at all -- surface it honestly rather than showing identical
    # output and letting the user think their edit was applied.
    if result.get("error"):
        print(f"\n  ⚠️  Couldn't apply that edit ({result['error']}) — posts are unchanged.\n")
        conversation["last_output"] = f"Edit failed: {result['error']}"
        return

    conversation["last_generated_posts"] = result["edited_posts"]

    state = create_initial_state(raw_prompt=instruction, session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = conversation.get("last_topic") or ""
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["generated_posts"] = conversation["last_generated_posts"]
    state["sources_used"] = []
    add_tokens(state, "content_generation", result["tokens_used"])
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")
    conversation["last_output"] = state["final_output"]


def _handle_add_constraint(args, conversation, verbose):
    from conversation.actions import add_constraint
    ctype, cvalue = args.get("constraint_type", "exclude"), args.get("constraint_value", "")
    result = add_constraint(ctype, cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"][-MAX_ACTIVE_CONSTRAINTS:]
    confirmation = f"✅ Got it — will {ctype} '{cvalue}' going forward."
    print(f"\n  {confirmation}\n")
    conversation["last_output"] = confirmation


def _handle_remove_constraint(args, conversation, verbose):
    from conversation.actions import remove_constraint
    cvalue = args.get("constraint_value", "")
    before = len(conversation.get("active_constraints", []))
    result = remove_constraint(cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"]
    after = len(conversation["active_constraints"])
    confirmation = (f"✅ Removed constraint on '{cvalue}'." if after < before
                    else f"ℹ️  No active constraint matching '{cvalue}' found.")
    print(f"\n  {confirmation}\n")
    conversation["last_output"] = confirmation


def _handle_clarify(args, conversation, verbose):
    question = args.get("clarify_question", "Could you clarify what you'd like me to do?")
    print(f"\n  🤔 {question}\n")
    conversation["last_output"] = question


def _handle_targeted_refetch(args, conversation, verbose):
    from conversation.actions import targeted_refetch
    from generation.content_generator import ContentGenerator
    from generation.formatter import format_output, save_output
    topic_delta = args.get("topic_delta", "")
    current_topic = conversation.get("last_topic") or ""
    refetch_result = targeted_refetch(topic_delta, current_topic,
                                       conversation.get("leftover_fetch_pool", []),
                                       conversation.get("active_constraints", []))
    state = create_initial_state(raw_prompt=f"{current_topic} {topic_delta}".strip(),
                                  session_id=str(uuid.uuid4())[:8])
    state["core_topic"] = f"{current_topic} ({topic_delta})".strip()
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["content_intent"] = conversation.get("last_content_intent") or "showcase"
    state["fetched_data"] = refetch_result["fetched_data"]
    state["total_items_fetched"] = sum(len(v) for v in refetch_result["fetched_data"].values())
    state["sources_used"] = list(refetch_result["fetched_data"].keys())
    state["active_constraints"] = conversation.get("active_constraints", [])
    state = ContentGenerator().generate(state)
    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")
    conversation["last_topic"] = state["core_topic"]
    conversation["last_generated_posts"] = state["generated_posts"]
    conversation["last_output"] = state["final_output"]
    conversation["leftover_fetch_pool"] = state.get("leftover_fetch_pool", [])


def dispatch_action(action, args, conversation, verbose, prompt="", platform=None, posts=5):
    handlers = {
        # FIX: now passes args through instead of discarding it.
        "run_new_request": lambda: _handle_run_new_request(args, prompt, platform, posts, verbose, conversation),
        "edit_existing": lambda: _handle_edit_existing(args, conversation, verbose),
        "add_constraint": lambda: _handle_add_constraint(args, conversation, verbose),
        "remove_constraint": lambda: _handle_remove_constraint(args, conversation, verbose),
        "targeted_refetch": lambda: _handle_targeted_refetch(args, conversation, verbose),
        "clarify": lambda: _handle_clarify(args, conversation, verbose),
    }
    fn = handlers.get(action)
    if fn is None:
        print(f"  ⚠️  Unknown action '{action}' — falling back to a fresh request.")
        fn = handlers["run_new_request"]
    fn()


def interactive_mode(verbose: bool = False):
    print_banner()
    print("  Interactive Mode — type anything, any length, any topic.")
    print("  Commands: last | verbose | quit\n")

    conversation = {
        "last_topic": None, "last_platform": None, "last_content_intent": None,
        "last_generated_posts": [], "last_output": None,
        "active_constraints": [], "leftover_fetch_pool": [],
        "message_history": [], "rolling_summary": "",
        "gate_tokens_used": 0,
    }

    while True:
        try:
            prompt = input("  Your idea: ").strip()
            if not prompt:
                continue
            if prompt.lower() == "quit":
                print("  Goodbye!")
                break
            if prompt.lower() == "last":
                print(conversation["last_output"] or "\n  No previous output yet this session.\n")
                continue
            if prompt.lower() == "verbose":
                verbose = not verbose
                print(f"\n  Verbose logging {'ON' if verbose else 'OFF'}.\n")
                continue

            prompt, platform, posts = _extract_flags(prompt)
            if platform is None and conversation["last_platform"]:
                platform = conversation["last_platform"]

            from conversation.orchestrator import process_turn, maybe_summarize, update_last_tool_result
            result = process_turn(conversation, prompt)
            conversation["gate_tokens_used"] += result.get("tokens_used", 0)

            if verbose:
                print(f"  [Orchestrator] action={result['action']} args={result['args']} "
                      f"tokens={result['tokens_used']} error={result['error']}")

            dispatch_action(result["action"], result["args"], conversation, verbose,
                             prompt=prompt, platform=platform, posts=posts)

            # FIX: previously the tool-call's recorded outcome in
            # message_history was just the literal string
            # "dispatched:{action_name}" -- content-free. This replaces
            # it with what actually happened (conversation["last_output"]
            # is already set by every handler above), so later turns'
            # sliding-window/summary context reflects real state instead
            # of a placeholder.
            update_last_tool_result(conversation, conversation.get("last_output") or "")

            maybe_summarize(conversation)

        except KeyboardInterrupt:
            print("\n  Goodbye!")
            break
        except Exception as e:
            print(f"  Error: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="TrendForge — Interactive Content Generator")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    interactive_mode(verbose=args.verbose)


if __name__ == "__main__":
    main()