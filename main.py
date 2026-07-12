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
from core.state import create_initial_state, get_total_tokens, add_log


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
    # Pulls previously-generated post titles/links for this topic+platform
    # from session history, so the generator can be told to avoid repeating
    # them. Wrapped defensively — a lookup failure should never block
    # generation, it should just mean this run has no "avoid" context.
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

    # Save to memory
    try:
        from memory.session_store import save_session
        save_session(state)
    except Exception as e:
        # Previously swallowed silently — a failed history save now leaves
        # a trace in the session's own log instead of vanishing with no
        # indication anywhere that history stopped saving.
        add_log(state, f"[Main] Session history save failed: {e}")

    elapsed = time.time() - start

    # Print final output
    print(state["final_output"])
    print(f"\n  ⏱  Completed in {elapsed:.1f}s")
    if saved_path:
        print(f"  💾 Saved to: {saved_path}")

    # Verbose: show agent logs
    if verbose and state.get("logs"):
        print("\n  📋 AGENT LOGS:")
        for log in state["logs"]:
            print(f"     {log}")

    # Non-fatal errors
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
    """
    Pulls --platform and --posts out of the prompt independently of each
    other and independently of order. The previous implementation chained
    sequential str.split() calls, so combining both flags in one line
    silently dropped whichever flag was written second (its value ended up
    inside the discarded half of an earlier split) depending purely on
    which flag appeared first in the text.
    """
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


def interactive_mode(verbose: bool = False):
    print_banner()
    print_status()
    print("  Interactive Mode — type anything, any length, any topic.")
    print("  Commands: status | history | last | verbose | quit\n")

    # In-session conversation memory — separate from the per-run
    # TrendForgeState created fresh inside run() on every call. This is
    # what previously did not exist at all: every interactive line got a
    # brand-new session_id and state, so generated_posts from the last
    # turn was discarded the moment the next line was typed. This dict
    # survives across turns within the same interactive session (it does
    # NOT persist across separate program runs — that's session_store.py's
    # job). Scope note: this only tracks the last turn's result, it does
    # not yet support addressing individual posts ("post 3") — that needs
    # the classifier/edit-path work, deliberately deferred.
    conversation = {
        "last_topic": None,
        "last_platform": None,
        "last_content_intent": None,
        "last_generated_posts": [],
        "last_output": None,
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
            # If the user didn't specify --platform this turn, default to
            # whatever platform they last used instead of always falling
            # back to run()'s hardcoded "instagram" default — a small,
            # safe improvement that needs no classifier.
            if platform is None and conversation["last_platform"]:
                platform = conversation["last_platform"]

            result = run(prompt, platform=platform, post_count=posts, verbose=verbose)

            conversation["last_topic"] = result.get("topic")
            conversation["last_platform"] = result.get("platform")
            conversation["last_content_intent"] = result.get("content_intent")
            conversation["last_generated_posts"] = result.get("posts", [])
            conversation["last_output"] = result.get("output")

        except KeyboardInterrupt:
            print("\n  Goodbye!")
            break
        except Exception as e:
            # Kept consistent with the graceful-degradation pattern used
            # throughout run() — a short message rather than a raw
            # traceback dump straight to the user.
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