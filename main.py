"""
main.py — TrendForge CLI Entrypoint

"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Config.config import SUPPORTED_PLATFORMS
from orchestration.dispatch import dispatch_action


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║         TRENDFORGE v1.0 — Trend Intelligence         ║
║   Real data. Any topic. Platform-ready content.      ║
╚══════════════════════════════════════════════════════╝""")


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

            from orchestration.conversation_agent import process_turn, maybe_summarize, update_last_tool_result
            result = process_turn(conversation, prompt)
            conversation["gate_tokens_used"] += result.get("tokens_used", 0)

            if verbose:
                print(f"  [Orchestrator] action={result['action']} args={result['args']} "
                      f"tokens={result['tokens_used']} error={result['error']}")

            dispatch_action(result["action"], result["args"], conversation, verbose,
                             prompt=prompt, platform=platform, posts=posts)

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