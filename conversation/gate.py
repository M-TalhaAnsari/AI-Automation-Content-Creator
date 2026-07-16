"""
conversation/gate.py — production-grade gate with layered logic.
Python owns the rules; the LLM is only a fallback for ambiguous cases.

Drop-in replacement: public function signatures (check_needs_history_and_action,
check_needs_history, resolve_action) are unchanged, so nothing else in the
project needs to change to use this file.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List

from config import CONFIG
from conversation.actions import ACTION_MAP

logger = logging.getLogger("conversation.gate")

# ------------------------------------------------------------------
# Guards
# ------------------------------------------------------------------
MAX_MESSAGE_LEN = 2000       # defensive cap before any regex/LLM touches the input
MAX_CONSTRAINT_VALUE_LEN = 200

# ------------------------------------------------------------------
# Deterministic Patterns
# ------------------------------------------------------------------
EXPLICIT_POST_REFERENCE = re.compile(r'\bpost\s*(\d+)\b', re.IGNORECASE)

ORDINAL_REFERENCE = re.compile(
    r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|'
    r'last|previous|next)\b',
    re.IGNORECASE
)
ORDINAL_WORDS = {
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
    'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
}

ACK_PATTERN = re.compile(
    r'^\s*(yes|no|ok|okay|sure|yep|nope|maybe|hello|hi|hey|thanks|thank\s+you|please|'
    r'better|again|more|less|why\?|perfect|great|good|bad|meh)\s*$',
    re.IGNORECASE
)

ADD_CONSTRAINT_PATTERN = re.compile(
    r"\b(don'?t\s+(use|mention|include|show|add)\s+|"
    r"avoid\s+|no\s+(more\s+)?|stop\s+(using|mentioning)\s+|"
    r"without\s+|exclude\s+|never\s+(use|mention)\s+|"
    r"remove\s+the\s+)",
    re.IGNORECASE
)
_ADD_VALUE_PATTERN = re.compile(
    r"(?:don'?t\s+(?:use|mention|include|show|add)\s+|"
    r"avoid\s+|no\s+(?:more\s+)?|stop\s+(?:using|mentioning)\s+|"
    r"without\s+|exclude\s+|never\s+(?:use|mention)\s+|"
    r"remove\s+the\s+)(.+)",
    re.IGNORECASE
)

REMOVE_CONSTRAINT_PATTERN = re.compile(
    r"\b(actually\s+)?(don'?t\s+(avoid|exclude|skip)|"
    r"include\s+\S+\s+now|keep\s+\S+|"
    r"no\s+need\s+to\s+(avoid|exclude)|"
    r"leave\s+\S+|stop\s+(avoiding|excluding))\b",
    re.IGNORECASE
)
_REMOVE_VALUE_PATTERN = re.compile(
    r"(?:don'?t\s+(?:avoid|exclude|skip)\s+(\S+(?:\s+\S+)*)|"
    r"include\s+(.+?)\s+now|"
    r"keep\s+(.+)|"
    r"no\s+need\s+to\s+(?:avoid|exclude)\s+(.+)|"
    r"leave\s+(.+)|"
    r"stop\s+(?:avoiding|excluding)\s+(.+))",
    re.IGNORECASE
)

_TRAILING_FILLER = re.compile(r'\b(please|thanks|thank you|okay|ok|now)\b\.?$', re.IGNORECASE)
_UNSAFE_CHARS = re.compile(r'[{}\[\]]')

VALID_ACTIONS = list(ACTION_MAP.keys()) + [
    "add_constraint", "remove_constraint", "run_new_request"
]

ACTION_ARG_SCHEMAS = {
    "edit_existing": {"target_posts": (list, str), "instruction": str},
    "add_constraint": {"constraint_type": str, "constraint_value": str},
    "remove_constraint": {"constraint_value": str},
    "targeted_refetch": {"topic_delta": str},
}

# ------------------------------------------------------------------
# Groq client -- lazily built once, reused, with a bounded timeout so a
# flaky network can't hang the whole conversation turn.
# ------------------------------------------------------------------
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=CONFIG.models.groq_api_key, timeout=10.0)
    return _groq_client


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _clean_value(raw: str) -> str:
    """Strip quoting/punctuation, cut at the first conjunction/comma so we
    don't sweep trailing chatter into the constraint, drop trailing filler
    words, strip characters that could break downstream JSON/prompt
    templates, and hard-cap the length."""
    value = raw.strip().rstrip('.').strip('"').strip("'")
    value = re.split(r'\s*[,;]\s*|\s+\band\b\s+|\s+\bbut\b\s+', value, maxsplit=1)[0]
    value = _TRAILING_FILLER.sub('', value).strip()
    value = _UNSAFE_CHARS.sub('', value).strip()
    return value[:MAX_CONSTRAINT_VALUE_LEN]


def _find_matching_constraint(value: str, active_constraints: List[Dict]) -> bool:
    """Only accept a deterministic remove_constraint when the extracted value
    plausibly refers to something actually active. Without this, patterns
    like 'keep it short' or 'keep going' false-positive as constraint
    removal (the 'keep \\S+' branch is intentionally loose upstream)."""
    if not value or not active_constraints:
        return False
    needle = value.lower()
    for c in active_constraints:
        cv = (c.get("value") or "").lower()
        if cv and (needle == cv or needle in cv or cv in needle):
            return True
    return False


def _resolve_ordinal(user_message: str, post_count: int) -> Optional[List[int]]:
    # Ranges: "first two", "last three"
    range_match = re.search(
        r'\b(first|last)\s+(two|three|four|five|six|seven|eight|nine|ten)\b',
        user_message, re.IGNORECASE
    )
    if range_match:
        direction = range_match.group(1).lower()
        count_word = range_match.group(2).lower()
        count = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}[count_word]
        if direction == 'first':
            return list(range(1, min(count, post_count) + 1))
        else:
            return list(range(max(1, post_count - count + 1), post_count + 1))

    # Single ordinal
    match = ORDINAL_REFERENCE.search(user_message)
    if not match:
        return None
    word = match.group(1).lower()
    if word == 'last':
        return [post_count]
    if word in ('previous', 'next'):
        return None
    if word in ORDINAL_WORDS:
        num = ORDINAL_WORDS[word]
        if 1 <= num <= post_count:
            return [num]
    return None


def _validate_args(action: str, args: dict, post_count: int) -> bool:
    if action == "run_new_request":
        return True
    if not isinstance(args, dict):
        return False
    schema = ACTION_ARG_SCHEMAS.get(action, {})
    for field, expected_type in schema.items():
        if field not in args:
            return False
        value = args[field]
        if expected_type == str:
            if not isinstance(value, str) or not value.strip():
                return False
            if len(value) > 500:
                return False
            cleaned = _UNSAFE_CHARS.sub('', value).strip()
            if not cleaned:
                return False
            args[field] = cleaned
        elif expected_type == (list, str):
            if isinstance(value, str):
                if value != "all":
                    return False
            elif isinstance(value, list):
                if not all(isinstance(i, int) and 1 <= i <= post_count for i in value):
                    return False
            else:
                return False
        if field == "constraint_type" and args.get(field) not in ("exclude", "prefer"):
            return False
    return True


# ------------------------------------------------------------------
# Main Gate
# ------------------------------------------------------------------
def check_needs_history_and_action(
    user_message: str,
    has_active_session: bool,
    last_topic: str = "",
    recent_messages: Optional[List[str]] = None,
    last_generated_posts: Optional[List[Dict]] = None,
    active_constraints: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    user_message = (user_message or "")[:MAX_MESSAGE_LEN]

    if not has_active_session:
        return {"needs_history": False, "method": "locked_no_session",
                "action": "run_new_request", "args": {}}

    posts = last_generated_posts or []
    post_count = len(posts)
    constraints = active_constraints or []

    # --- Stage 1: Deterministic checks ---
    # Explicit post number
    m = EXPLICIT_POST_REFERENCE.search(user_message)
    if m:
        num = int(m.group(1))
        if 1 <= num <= post_count:
            return {"needs_history": True, "method": "deterministic_reference",
                    "action": "edit_existing",
                    "args": {"target_posts": [num], "instruction": user_message}}

    # Ordinal references
    ords = _resolve_ordinal(user_message, post_count) if post_count else None
    if ords:
        return {"needs_history": True, "method": "deterministic_ordinal",
                "action": "edit_existing",
                "args": {"target_posts": ords, "instruction": user_message}}

    # Acknowledgments
    if ACK_PATTERN.match(user_message):
        return {"needs_history": True, "method": "deterministic_ack",
                "action": "edit_existing",
                "args": {"target_posts": "all", "instruction": user_message}}

    # Add constraint
    if ADD_CONSTRAINT_PATTERN.search(user_message):
        value_match = _ADD_VALUE_PATTERN.search(user_message)
        cv = _clean_value(value_match.group(1)) if value_match else ""
        if cv:
            return {"needs_history": True, "method": "deterministic_add_constraint",
                    "action": "add_constraint",
                    "args": {"constraint_type": "exclude", "constraint_value": cv}}
        # extraction failed to produce anything usable -- don't guess, fall through

    # Remove constraint
    if REMOVE_CONSTRAINT_PATTERN.search(user_message):
        removal_match = _REMOVE_VALUE_PATTERN.search(user_message)
        if removal_match:
            groups = removal_match.groups()
            raw_value = next((g for g in groups if g), "")
            cv = _clean_value(raw_value)
            # Only trust this deterministically if it actually matches
            # something currently active -- kills false positives like
            # "keep it short" being read as constraint removal.
            if _find_matching_constraint(cv, constraints):
                return {"needs_history": True, "method": "deterministic_remove_constraint",
                        "action": "remove_constraint",
                        "args": {"constraint_value": cv}}
            # else fall through to LLM stage for disambiguation

    # --- Stage 2: LLM fallback ---
    try:
        client = _get_groq_client()
        posts_list = "\n".join(f"{i}. {p['title']}" for i, p in enumerate(posts, 1))
        constraints_list = ", ".join(
            f"{c['type']}:{c['value']}" for c in constraints
        ) or "none"

        system_prompt = (
            "You are a lightweight conversation router. Given the user message and session context, "
            "output ONLY a JSON object with: needs_history (bool), action (one of edit_existing, "
            "add_constraint, remove_constraint, targeted_refetch, run_new_request), and args (dict).\n"
            "Do NOT resolve exact post numbers — only output the intent and the raw instruction."
        )
        user_prompt = f"""Context:
- Topic: {last_topic}
- Numbered posts:
{posts_list}
- Active constraints: {constraints_list}

User message: "{user_message}"

Which action should be taken? JSON:"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
    except Exception as e:
        logger.warning("LLM gate fallback failed (%s: %s); defaulting to run_new_request.",
                        type(e).__name__, e)
        return {"needs_history": False, "method": "llm_error_fallback",
                "action": "run_new_request", "args": {}}

    needs = parsed.get("needs_history", False)
    action = parsed.get("action", "run_new_request")
    args = parsed.get("args", {})

    # --- Stage 3: Reference resolution ---
    if needs and action == "edit_existing":
        target = args.get("target_posts")
        if isinstance(target, str) and target != "all":
            resolved = _resolve_ordinal(target, post_count)
            args["target_posts"] = resolved if resolved else "all"
        elif isinstance(target, list):
            if not (all(isinstance(i, int) and 1 <= i <= post_count for i in target)):
                args["target_posts"] = "all"

    # --- Stage 4: Validation ---
    if not _validate_args(action, args, post_count):
        logger.info("LLM proposed action '%s' failed validation; defaulting to run_new_request.", action)
        action = "run_new_request"
        args = {}
    if action not in VALID_ACTIONS:
        logger.info("LLM proposed unknown action '%s'; defaulting to run_new_request.", action)
        action = "run_new_request"
        args = {}

    return {"needs_history": needs, "method": "llm_fallback",
            "action": action, "args": args}


def check_needs_history(*args, **kwargs):
    result = check_needs_history_and_action(*args, **kwargs)
    return {"needs_history": result["needs_history"], "method": result["method"]}


def resolve_action(user_message, recent_context):
    result = check_needs_history_and_action(
        user_message,
        has_active_session=True,
        last_topic=recent_context.get("last_topic", ""),
        recent_messages=recent_context.get("recent_messages", []),
        last_generated_posts=recent_context.get("last_generated_posts", []),
        active_constraints=recent_context.get("active_constraints", []),
    )
    return {"action": result["action"], "args": result["args"]} if result["needs_history"] else {"action": "run_new_request", "args": {}}