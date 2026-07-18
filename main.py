"""
main.py — TrendForge Final Runner

Usage:
    python main.py "top ML projects for instagram"
    python main.py --platform tiktok "discipline motivation"
    python main.py --posts 3 "AI startups 2026 linkedin"
    python main.py --interactive
    python main.py --history
    python main.py --status
"""

import sys, os, uuid, time, argparse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG, SUPPORTED_PLATFORMS
from core.state import create_initial_state, get_total_tokens, add_log, add_tokens

# ── Phase 2: conversation-level session growth caps ────────────────
MAX_ACTIVE_CONSTRAINTS = 20
MAX_RECENT_MESSAGES = 5


# ─────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────

def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║         TRENDFORGE v1.0 — Trend Intelligence         ║
║   Real data. Any topic. Platform-ready content.      ║
╚══════════════════════════════════════════════════════╝""")


def print_status():
    print("\n  SYSTEM STATUS")
    print("  " + "─" * 42)
    print(f"  {'✅' if CONFIG.models.groq_api_key   else '❌'} Groq ({CONFIG.models.groq_model_small})  — parsing + routing")
    print(f"  {'✅' if CONFIG.models.gemini_api_key else '❌'} Gemini ({CONFIG.models.gemini_model}) — content generation")
    print("\n  DATA SOURCES")
    print("  " + "─" * 42)
    from routing.registry import get_source_display_info
    for s in get_source_display_info():
        icon = "✅" if s["available"] else "⚠️ "
        key_note = f"(needs {s['key_env_var']})" if s["requires_key"] and not s["available"] else f"({s['freshness']})"
        print(f"  {icon} {s['display_name']:<24} {key_note}")
    critical = [w for w in CONFIG.validate() if "fail" in w.lower()]
    if critical:
        print("\n  ❌ MISSING (required):")
        for w in critical:
            print(f"     • {w}")
    print()


def print_history():
    from memory.session_store import get_history
    sessions = get_history(10)
    if not sessions:
        print("\n  No history yet.\n")
        return
    print(f"\n  LAST {len(sessions)} SESSIONS")
    print("  " + "─" * 50)
    for s in reversed(sessions):
        ts = s["timestamp"][:16].replace("T", " ")
        print(f"  [{ts}] [{s['platform']}] {s['topic']}")
        print(f"         tokens={s['total_tokens']} | sources={s['sources_used']}")
    print()


# ─────────────────────────────────────────────
# CORE PIPELINE
# ─────────────────────────────────────────────

def run(prompt: str, platform: str = None, post_count: int = 5, verbose: bool = False) -> dict:

    start = time.time()
    session_id = str(uuid.uuid4())[:8]
    state = create_initial_state(raw_prompt=prompt, session_id=session_id)
    if platform and platform in SUPPORTED_PLATFORMS:
        state["platform"] = platform
    if post_count:
        state["post_count"] = post_count

    print(f"\n  ┌─ Session: {session_id}")
    print(f"  │  Prompt:  \"{prompt[:72]}{'...' if len(prompt)>72 else ''}\"")
    print(f"  └─ Platform: {state['platform']} | Posts: {state['post_count']}\n")

    # ── STEP 1: PROMPT PARSER ────────────────────────────────
    print("  [1/5] 🧠 Understanding prompt...")
    try:
        from understanding.prompt_parser import PromptParser
        state = PromptParser().parse(state)
        print(f"        ✅ topic='{state['core_topic']}' | "
              f"platform={state['platform']} | "
              f"category={state['detected_category']} | "
              f"tokens={state['tokens']['prompt_parsing']}")
    except Exception as e:
        print(f"        ⚠️  Parser error: {e} — using raw prompt")
        state["core_topic"] = prompt[:60]

    # ── STEP 2: SOURCE ROUTER ────────────────────────────────
    print("  [2/5] 🔀 Selecting sources...")
    try:
        from routing.router_orchestrator import RouterOrchestrator
        state = RouterOrchestrator().route(state)
        print(f"        ✅ sources={state['selected_sources']} "
              f"| method={state['routing_method']} "
              f"| tokens={state['tokens']['source_routing']}")
    except Exception as e:
        print(f"        ⚠️  Router error: {e} — using defaults")
        state["selected_sources"] = ["google_trends", "hackernews"]

    # ── STEP 3: DATA FETCHERS ────────────────────────────────
    print("  [3/5] 🌐 Fetching live data...")
    try:
        from fetchers.fetcher_orchestrator import FetcherOrchestrator
        state = FetcherOrchestrator().fetch(state)
        print(f"        ✅ {state['total_items_fetched']} items "
              f"from {state['sources_used']}")
    except ImportError:
        state["fetched_data"] = {}
        state["total_items_fetched"] = 0
        state["sources_used"] = []
        print("        ⚠️  Fetchers not found — Gemini uses training knowledge")
    except Exception as e:
        state["fetched_data"] = {}
        state["total_items_fetched"] = 0
        state["sources_used"] = []
        print(f"        ⚠️  Fetch error: {e} — continuing without live data")

    # ── ALREADY-COVERED LOOKUP ───────────────────────────────
    try:
        from memory.session_store import get_already_covered
        state["already_covered"] = get_already_covered(state["core_topic"], state["platform"])
        if state["already_covered"]:
            add_log(state, f"[Main] Found {len(state['already_covered'])} previously-covered items for this topic/platform")
    except Exception as e:
        state["already_covered"] = []
        add_log(state, f"[Main] Already-covered lookup skipped: {e}")

    # ── STEP 4: CONTENT GENERATOR ────────────────────────────
    print("  [4/5] ✨ Generating content (Gemini 2.0 Flash)...")
    try:
        from generation.content_generator import ContentGenerator
        state = ContentGenerator().generate(state)
        print(f"        ✅ {len(state['generated_posts'])} posts generated "
              f"| tokens={state['tokens']['content_generation']}")
    except Exception as e:
        print(f"        ❌ Generation failed: {e}")
        state["generated_posts"] = []

    # ── STEP 5: FORMAT + TOKEN REPORT + SAVE ─────────────────
    print("  [5/5] 📦 Formatting output...\n")
    from generation.formatter import format_output, save_output
    state = format_output(state)
    saved_path = save_output(state)

    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        add_log(state, f"[Main] Session history save failed: {e}")

    elapsed = time.time() - start

    print(state["final_output"])
    print(f"\n  ⏱  Completed in {elapsed:.1f}s")
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")

    if verbose and state.get("logs"):
        print("\n  📋 AGENT LOGS:")
        for log in state["logs"]:
            print(f"     {log}")

    if state["errors"]:
        print("\n  ⚠️  Warnings:")
        for e in state["errors"]:
            print(f"     • {e}")

    return {
        "output":     state["final_output"],
        "session_id": session_id,
        "tokens":     state["tokens"],
        "total_tokens": get_total_tokens(state),
        "errors":     state["errors"],
        "posts":      state["generated_posts"],
        "topic":      state.get("core_topic", ""),
        "platform":   state.get("platform", ""),
        "content_intent": state.get("content_intent", ""),
    }


# ─────────────────────────────────────────────
# INTERACTIVE MODE
# ─────────────────────────────────────────────

def _extract_flags(prompt: str):
    platform = None
    posts = 5

    platform_match = re.search(r'--platform\s+(\S+)', prompt)
    if platform_match and platform_match.group(1) in SUPPORTED_PLATFORMS:
        platform = platform_match.group(1)
        prompt = prompt.replace(platform_match.group(0), '').strip()

    posts_match = re.search(r'--posts\s+(\d+)', prompt)
    if posts_match:
        posts = int(posts_match.group(1))
        prompt = prompt.replace(posts_match.group(0), '').strip()

    return prompt.strip(), platform, posts


# ─────────────────────────────────────────────
# PHASE 2: ACTION DISPATCH HANDLERS
# ─────────────────────────────────────────────

def _handle_run_new_request(prompt: str, platform, posts: int, verbose: bool, conversation: dict):
    """Unchanged existing behavior — the gate decided this is a fresh,
    unrelated request, so it goes through the normal full pipeline.

    KNOWN GAP: active_constraints is NOT threaded into this path yet.
    """
    if verbose:
        print(f"  [Gate] -> run_new_request (full pipeline, unchanged)")
    result = run(prompt, platform=platform, post_count=posts, verbose=verbose)
    conversation["last_topic"] = result.get("topic")
    conversation["last_platform"] = result.get("platform")
    conversation["last_content_intent"] = result.get("content_intent")
    conversation["last_generated_posts"] = result.get("posts", [])
    conversation["last_output"] = result.get("output")


def _handle_edit_existing(args: dict, conversation: dict, verbose: bool):
    from conversation.actions import edit_existing
    from generation.formatter import format_output, save_output
    import uuid as _uuid

    target_posts = args.get("target_posts", "all")
    instruction = args.get("instruction", "")
    if verbose:
        print(f"  [Gate] -> edit_existing(target_posts={target_posts!r}, instruction={instruction!r})")

    result = edit_existing(target_posts, instruction, conversation.get("last_generated_posts", []))
    conversation["last_generated_posts"] = result["edited_posts"]
    if verbose:
        print(f"  [Gate] edit_existing used {result['tokens_used']} tokens")

    state = create_initial_state(raw_prompt=instruction, session_id=str(_uuid.uuid4())[:8])
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


def _handle_add_constraint(args: dict, conversation: dict, verbose: bool):
    from conversation.actions import add_constraint

    ctype = args.get("constraint_type", "exclude")
    cvalue = args.get("constraint_value", "")
    if verbose:
        print(f"  [Gate] -> add_constraint(type={ctype!r}, value={cvalue!r})")

    result = add_constraint(ctype, cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"][-MAX_ACTIVE_CONSTRAINTS:]

    confirmation = f"✅ Got it — will {ctype} '{cvalue}' going forward."
    print(f"\n  {confirmation}")
    if verbose:
        print(f"  [Gate] active_constraints now: {conversation['active_constraints']}")
    print()

    # NEW: any caller (CLI or web) can now read "what should the user see"
    # uniformly from conversation['last_output'], regardless of which
    # action fired -- previously only edit_existing/run_new_request/
    # targeted_refetch set this, so a web layer had no way to retrieve
    # this confirmation message after the fact.
    conversation["last_output"] = confirmation


def _handle_remove_constraint(args: dict, conversation: dict, verbose: bool):
    from conversation.actions import remove_constraint

    cvalue = args.get("constraint_value", "")
    if verbose:
        print(f"  [Gate] -> remove_constraint(value={cvalue!r})")

    before = len(conversation.get("active_constraints", []))
    result = remove_constraint(cvalue, conversation.get("active_constraints", []))
    conversation["active_constraints"] = result["active_constraints"]
    after = len(conversation["active_constraints"])

    if after < before:
        confirmation = f"✅ Removed constraint on '{cvalue}'."
    else:
        confirmation = f"ℹ️  No active constraint matching '{cvalue}' was found — nothing changed."
    print(f"\n  {confirmation}")
    if verbose:
        print(f"  [Gate] active_constraints now: {conversation['active_constraints']}")
    print()

    # NEW: same reasoning as _handle_add_constraint above.
    conversation["last_output"] = confirmation


def _handle_targeted_refetch(args: dict, conversation: dict, verbose: bool):
    from conversation.actions import targeted_refetch
    from generation.content_generator import ContentGenerator
    from generation.formatter import format_output, save_output
    import uuid as _uuid

    topic_delta = args.get("topic_delta", "")
    current_topic = conversation.get("last_topic") or ""
    if verbose:
        print(f"  [Gate] -> targeted_refetch(topic_delta={topic_delta!r}, current_topic={current_topic!r})")

    refetch_result = targeted_refetch(
        topic_delta, current_topic,
        conversation.get("leftover_fetch_pool", []),
        conversation.get("active_constraints", []),
    )
    if verbose:
        print(f"  [Gate] used_leftover_pool={refetch_result['used_leftover_pool']}")

    state = create_initial_state(raw_prompt=f"{current_topic} {topic_delta}".strip(),
                                  session_id=str(_uuid.uuid4())[:8])
    state["core_topic"] = f"{current_topic} ({topic_delta})".strip()
    state["platform"] = conversation.get("last_platform") or "instagram"
    state["content_intent"] = conversation.get("last_content_intent") or "showcase"
    state["fetched_data"] = refetch_result["fetched_data"]
    state["total_items_fetched"] = sum(len(v) for v in refetch_result["fetched_data"].values())
    state["sources_used"] = list(refetch_result["fetched_data"].keys())
    state["active_constraints"] = conversation.get("active_constraints", [])

    if verbose:
        print(f"  [Gate] Generating content from {'leftover pool' if refetch_result['used_leftover_pool'] else 'new fetch'}...")
    state = ContentGenerator().generate(state)
    if verbose:
        print(f"  [Gate] {len(state['generated_posts'])} posts generated | tokens={state['tokens']['content_generation']}")

    state = format_output(state)
    saved_path = save_output(state)
    print(state["final_output"])
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")

    conversation["last_topic"] = state["core_topic"]
    conversation["last_generated_posts"] = state["generated_posts"]
    conversation["last_output"] = state["final_output"]
    conversation["leftover_fetch_pool"] = state.get("leftover_fetch_pool", [])


# ─────────────────────────────────────────────
# NEW: shared gate-resolution step
# ─────────────────────────────────────────────
# Previously this logic (has_active_session computation, the gate call,
# verbose printing, recent_messages bookkeeping) was inlined directly in
# interactive_mode()'s while loop. Pulled out unchanged so a web request
# handler can call the exact same decision logic the CLI uses, instead of
# re-implementing or duplicating it. interactive_mode() below calls this
# and is otherwise identical to before.

def resolve_turn(prompt: str, conversation: dict, verbose: bool = False) -> dict:
    """Runs the gate against one message + the given conversation state.
    Mutates conversation['recent_messages'] as a side effect (unchanged
    behavior). Returns the raw gate result dict."""
    has_active_session = bool(conversation.get("last_generated_posts"))
    if verbose:
        print(f"  [Gate] has_active_session={has_active_session}")

    from conversation.gate import check_needs_history_and_action
    gate_result = check_needs_history_and_action(
        user_message=prompt,
        has_active_session=has_active_session,
        last_topic=conversation.get("last_topic") or "",
        recent_messages=conversation.get("recent_messages", []),
        last_generated_posts=conversation.get("last_generated_posts", []),
        active_constraints=conversation.get("active_constraints", []),
    )
    if verbose:
        print(f"  [Gate] needs_history={gate_result['needs_history']} "
              f"method={gate_result['method']} action={gate_result['action']} "
              f"args={gate_result['args']}")

    conversation.setdefault("recent_messages", [])
    conversation["recent_messages"].append(prompt)
    conversation["recent_messages"] = conversation["recent_messages"][-MAX_RECENT_MESSAGES:]

    return gate_result


def dispatch_action(action: str, args: dict, conversation: dict, verbose: bool,
                     prompt: str = "", platform=None, posts: int = 5):
    """Runs the handler for an already-resolved action. Split out from
    resolve_turn so the web layer can enqueue the slow actions
    (run_new_request/edit_existing/targeted_refetch) as background jobs
    while still calling the cheap ones (add/remove_constraint) inline --
    see web/jobs.py."""
    if action == "run_new_request":
        _handle_run_new_request(prompt, platform, posts, verbose, conversation)
    elif action == "edit_existing":
        _handle_edit_existing(args, conversation, verbose)
    elif action == "add_constraint":
        _handle_add_constraint(args, conversation, verbose)
    elif action == "remove_constraint":
        _handle_remove_constraint(args, conversation, verbose)
    elif action == "targeted_refetch":
        _handle_targeted_refetch(args, conversation, verbose)
    else:
        print(f"  ⚠️  Unknown action '{action}' from gate — falling back to a fresh request.")
        _handle_run_new_request(prompt, platform, posts, verbose, conversation)


def interactive_mode(verbose: bool = False):
    print_banner()
    print_status()
    print("  Interactive Mode — type anything, any length, any topic.")
    print("  Commands: status | history | last | verbose | quit\n")

    conversation = {
        "last_topic": None,
        "last_platform": None,
        "last_content_intent": None,
        "last_generated_posts": [],
        "last_output": None,
        "active_constraints": [],
        "leftover_fetch_pool": [],
        "recent_messages": [],
    }

    while True:
        try:
            prompt = input("  Your idea: ").strip()
            if not prompt:
                continue
            if prompt.lower() == "quit":
                print("  Goodbye!")
                break
            if prompt.lower() == "status":
                print_status()
                continue
            if prompt.lower() == "history":
                print_history()
                continue
            if prompt.lower() == "last":
                if conversation["last_output"]:
                    print(conversation["last_output"])
                else:
                    print("\n  No previous output yet this session.\n")
                continue
            if prompt.lower() == "verbose":
                verbose = not verbose
                print(f"\n  Verbose logging {'ON' if verbose else 'OFF'}.\n")
                continue

            prompt, platform, posts = _extract_flags(prompt)
            if platform is None and conversation["last_platform"]:
                platform = conversation["last_platform"]

            gate_result = resolve_turn(prompt, conversation, verbose)
            action = gate_result.get("action", "run_new_request")
            args = gate_result.get("args", {})

            dispatch_action(action, args, conversation, verbose,
                             prompt=prompt, platform=platform, posts=posts)

        except KeyboardInterrupt:
            print("\n  Goodbye!")
            break
        except Exception as e:
            print(f"  Error: {e}")


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TrendForge — Universal Trend Intelligence + Content Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "top ML projects for instagram"
  python main.py --platform tiktok "discipline motivation"
  python main.py --posts 3 "AI startups 2026"
  python main.py --interactive
  python main.py --history
  python main.py --status
        """
    )
    parser.add_argument("prompt",        nargs="?",  help="Your content idea (any length)")
    parser.add_argument("--platform",    choices=SUPPORTED_PLATFORMS, default=None)
    parser.add_argument("--posts",       type=int,   default=5)
    parser.add_argument("--verbose","-v",action="store_true", help="Show agent logs")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--history",     action="store_true", help="Show past sessions")
    parser.add_argument("--status",      action="store_true", help="Show system status")
    args = parser.parse_args()

    print_banner()

    if args.status:
        print_status()
        return
    if args.history:
        print_history()
        return
    if args.interactive or not args.prompt:
        interactive_mode(verbose=args.verbose)
        return

    print_status()
    run(args.prompt, platform=args.platform,
        post_count=args.posts, verbose=args.verbose)


if __name__ == "__main__":
    main()