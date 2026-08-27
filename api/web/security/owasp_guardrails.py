"""
api/web/security/owasp_guardrails.py -- OWASP LLM Top 10 Security Guardrails.

Implements:
- LLM01: Prompt Injection & Jailbreak Defense
- LLM02: Sensitive Information & PII Scrubbing
- LLM04: Model Denial of Service & Token Flooding Protection
- LLM07: System Prompt Leakage Defense
"""
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("aiflick.security.owasp")

# ── 1. Prompt Injection & Jailbreak Patterns ──────────────────────────────────
_JAILBREAK_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)\b",
    r"(?i)\bdisregard\s+(all\s+)?(safety|system|guidelines|instructions)\b",
    r"(?i)\breveal\s+(the\s+)?(system\s+prompt|developer\s+mode|secret\s+key|instructions)\b",
    r"(?i)\bprint\s+(the\s+)?(system\s+prompt|initial\s+prompt|hidden\s+text)\b",
    r"(?i)\byou\s+are\s+now\s+in\s+developer\s+mode\b",
    r"(?i)\bdo\s+anything\s+now\b",
    r"(?i)\bjailbreak\b",
    r"(?i)\boutput\s+the\s+entire\s+prompt\b",
]

# ── 2. PII & API Secret Scrubbing Patterns ─────────────────────────────────────
_SECRET_PATTERNS = [
    (r"(?i)\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED_API_KEY]"),
    (r"(?i)\b(ghp_[a-zA-Z0-9]{30,})\b", "[REDACTED_GITHUB_TOKEN]"),
    (r"(?i)\b(AIzaSy[a-zA-Z0-9_-]{33})\b", "[REDACTED_GEMINI_KEY]"),
    (r"(?i)\b(xox[baprs]-[a-zA-Z0-9]{10,})\b", "[REDACTED_SLACK_TOKEN]"),
    (r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", "[USER_EMAIL_MASKED]"),
    (r"\b\+?[0-9]{1,3}?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b", "[PHONE_MASKED]"),
]

# Max characters per user prompt
MAX_PROMPT_LENGTH = 2500


def sanitize_and_validate_prompt(prompt: str) -> Tuple[str, bool, Optional[str]]:
    """
    Sanitize user prompt for OWASP LLM Top 10 vulnerabilities.

    Returns:
        (sanitized_prompt, is_safe, warning_or_reason)
    """
    if not prompt or not prompt.strip():
        return "", True, None

    # 1. DoS / Token Flooding Hard Cap
    cleaned = prompt.strip()
    if len(cleaned) > MAX_PROMPT_LENGTH:
        cleaned = cleaned[:MAX_PROMPT_LENGTH]
        logger.warning("Prompt truncated due to exceeding MAX_PROMPT_LENGTH (%d)", MAX_PROMPT_LENGTH)

    # 2. Jailbreak / Injection Detection
    for pattern in _JAILBREAK_PATTERNS:
        if re.search(pattern, cleaned):
            logger.warning("OWASP LLM01: Potential prompt injection blocked: pattern '%s'", pattern)
            # Defang the malicious instruction by wrapping in safety context
            sanitized = re.sub(pattern, "[FILTERED_OVERRIDE_ATTEMPT]", cleaned)
            return sanitized, False, "Potential prompt injection or override pattern neutralized."

    # 3. Secret & PII Sanitization
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = re.sub(pattern, replacement, cleaned)

    return cleaned, True, None


def wrap_boundary_tags(user_input: str, grounding_data: Optional[str] = None) -> str:
    """
    Wrap context and user input inside structural XML-like boundary tags
    to prevent context confusion / injection attacks (OWASP LLM07 defense).
    """
    wrapped = "<USER_INPUT>\n" + user_input.strip() + "\n</USER_INPUT>"
    if grounding_data:
        wrapped = f"<RESEARCH_SIGNALS>\n{grounding_data.strip()}\n</RESEARCH_SIGNALS>\n\n" + wrapped
    return wrapped
