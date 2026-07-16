"""
test_gate_failures.py — QA stress script designed to break the current gate.

Run this WITHOUT a Groq API key (or with a mock that never gets called).
The goal is to find messages that the deterministic layers misclassify.
"""

from conversation.gate import check_needs_history_and_action

# A typical active session context – just enough to let the gate run.
ACTIVE_CTX = {
    "last_topic": "AI Security",
    "recent_messages": ["Generate 5 posts about AI Security"],
    "last_generated_posts": [
        {"title": "Prompt Injection"},
        {"title": "Skeleton Key"},
        {"title": "Crescendo"},
        {"title": "Goal Hijacking"},
        {"title": "Data Poisoning"},
    ],
    "active_constraints": [],
}

def run_test(description, user_msg, expected_action, expected_args_part=None):
    """Return True if the gate matches the expected action (and partial args)."""
    res = check_needs_history_and_action(user_msg, True, **ACTIVE_CTX)
    action = res["action"]
    args = res["args"]
    # Check action
    if action != expected_action:
        print(f"❌ FAIL [{description}]: expected action '{expected_action}', got '{action}'")
        return False
    # Optionally check for a substring in instruction or constraint_value
    if expected_args_part:
        if action == "edit_existing":
            instr = args.get("instruction", "")
            if expected_args_part not in instr:
                print(f"❌ FAIL [{description}]: instruction doesn't contain '{expected_args_part}': {instr}")
                return False
        elif action in ("add_constraint", "remove_constraint"):
            value = args.get("constraint_value", "")
            if expected_args_part not in value:
                print(f"❌ FAIL [{description}]: constraint_value doesn't contain '{expected_args_part}': {value}")
                return False
        elif action == "targeted_refetch":
            delta = args.get("topic_delta", "")
            if expected_args_part not in delta:
                print(f"❌ FAIL [{description}]: topic_delta doesn't contain '{expected_args_part}': {delta}")
                return False
    print(f"✅ PASS [{description}]")
    return True

# ------------------------------------------------------------------
# Tests that SHOULD be new_request, but are likely caught as add_constraint
# ------------------------------------------------------------------
tests = [
    # "remove the" false positive
    ("'remove the' mis‑fired", "Please remove the old files from the list",
     "run_new_request", None),   # we expect this to be a new request, not a constraint
    ("'remove the' mis‑fired 2", "I will remove the stains later",
     "run_new_request", None),

    # "without" false positive
    ("'without' mis‑fired", "Without a doubt, this is the best",
     "run_new_request", None),
    ("'without' mis‑fired 2", "I can't live without you",
     "run_new_request", None),

    # "stop using" might be fine, but let's test an edge: "stop using that tone"
    # Actually that could be a valid constraint, but in a generic conversation it might not be.
    # We'll skip that.

    # "keep" (in REMOVE_CONSTRAINT_PATTERN) could false‑fire on "Keep the change"
    # But that pattern only triggers if an active constraint matches, so unless we have "change" as constraint, it won't fire. Safe.

    # Test ordinal reference when post_count = 0 (no posts)
    # We'll create a context with no generated posts.
]

# Additional context without posts
EMPTY_POSTS_CTX = {
    "last_topic": "AI Security",
    "recent_messages": ["Generate 5 posts"],
    "last_generated_posts": [],
    "active_constraints": [],
}

# Test ordinal in a session with no posts – should fall through, not crash
res = check_needs_history_and_action("The third one is boring", True, **EMPTY_POSTS_CTX)
if res["action"] != "run_new_request":  # because ordinal resolution returns None -> falls to LLM -> but we haven't mocked, so it will attempt LLM call and fail unless Groq key present. We'll skip.
    print("Ordinal on empty posts didn't crash (expected fallback)")

# For the script to run without API, we can patch groq.Groq to return a dummy, but the point is to test deterministic rules. The above false‑positive tests will run without any LLM call because the deterministic add_constraint catches them before the LLM stage. So they are safe to run offline.

if __name__ == "__main__":
    passed = 0
    failed = 0
    for desc, msg, exp_act, exp_args in tests:
        if run_test(desc, msg, exp_act, exp_args):
            passed += 1
        else:
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests.")