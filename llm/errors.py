"""
llm/errors.py — Exceptions raised by the LLM gateway (llm/client.py).

Only these two. Every LLM-related failure in the system is either one
of these, or an exception from network/SDK plumbing that llm/client.py
deliberately doesn't swallow (see _call_with_retry's final raise).
"""

from __future__ import annotations

from typing import Any


class LLMCallFailed(Exception):
    """
    The provider call itself failed — network error, timeout, non-2xx
    response, or a rate limit that didn't clear within the gateway's
    retry budget.

    Distinct from LLMSchemaViolation: the request never got a usable
    response back at all, as opposed to getting one that doesn't match
    what was asked for.
    """


class LLMSchemaViolation(Exception):
    """
    A response was received but does not validate against the
    requested Pydantic schema — whether because the provider ignored
    the schema, only partially enforced it, or returned malformed JSON.

    This is a hard error. llm/client.py does NOT attempt prose-repair
    parsing or a silent same-prompt retry when this is raised — per
    ARCHITECTURE.md §2, that decision belongs to the caller (retry with
    a stricter prompt, fall back to a rule-based default, or fall back
    to the other provider — whichever fits that call site).
    """

    def __init__(
        self,
        message: str,
        raw_response: str | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.validation_errors = validation_errors or []