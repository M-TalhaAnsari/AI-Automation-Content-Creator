"""
llm/client.py — The LLM Gateway (ARCHITECTURE.md §2).

This is the ONLY file in the codebase allowed to import `groq` or
`google.genai`. Every other file gets an LLM response through
call_groq() / call_gemini() below — see ARCHITECTURE.md principle #3.

Design decisions baked into this file:

  Schemas are Pydantic models (llm/schemas.py), not hand-written
  JSON-schema dicts. We generate the provider-facing JSON schema from
  the model (`schema.model_json_schema()`), but we ALSO always
  re-validate the raw response against that same model locally before
  returning — provider-side enforcement is treated as a latency/cost
  optimization, not a substitute for local validation:
    - Groq's structured outputs are "strict" (constrained decoding,
      guaranteed schema-compliant) only on supported models; other
      models get "best-effort" support, which can still error.
    - Gemini's response_schema historically has been a subset of
      OpenAPI/JSON Schema, and keyword support has been a moving
      target across SDK versions — not something to trust blindly for
      a constraint like the hashtag "^#" pattern without checking your
      pinned SDK version actually enforces it.
  Local validation via model_validate_json() is what actually delivers
  the "hard error on violation, no prose-repair" contract this module
  promises — not the provider's own claim of enforcement.

  LLMResult.content is a plain dict (`model.model_dump()`), not the
  Pydantic instance. Every existing call site in ARCHITECTURE.md §3
  reads `.get(...)` off `llm_result.content` (e.g.
  intent_extractor.py's `llm.get("core_topic")`) and is expected to
  keep doing so — this file changes how validation happens internally,
  not the shape callers see. That's a deliberate scope limit: making
  LLMResult.content a typed Pydantic object would be strictly nicer for
  callers but would ripple into a call-site change in nearly every
  file §3 touches, which cuts against "make only the change the entry
  says." Revisit only as a deliberate, separately-scoped follow-up.

  Token tracking: this module returns `tokens_used`; it does NOT call
  add_tokens() itself. Callers own writing to their own state's token
  category ("prompt_parsing", "content_generation", etc.) — only the
  caller knows which category applies.

Retry policy (PERFORMANCE_AND_RESILIENCE.md §2.3): one policy, defined
once, here — not a try/except per call site. It only covers
TRANSIENT/SYSTEMIC failures (network errors, timeouts, rate limits,
5xx). It never retries on LLMSchemaViolation; that's a hard error the
caller decides how to handle (see agents/02_intent_agent.md's "Must
NOT do" — no prose-repair cascades).

ASSUMPTION FLAGGED, NOT VERIFIED: `Config.config.CONFIG.models` is
assumed to expose `groq_api_key` (confirmed — used as-is in the current
understanding/intent_extractor.py) and `gemini_api_key` (NOT confirmed
— config/ is listed in ARCHITECTURE.md §6 as not-yet-audited). If the
real attribute name differs, only `_lazy_genai_client()` below needs
to change.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types as genai_types
from groq import Groq
from pydantic import BaseModel, ValidationError

from llm.errors import LLMCallFailed, LLMSchemaViolation

logger = logging.getLogger("trendforge.llm")

# ── Retry policy ──────────────────────────────────────────────
_MAX_RETRIES = 2
_BACKOFF_BASE_SECONDS = 1.5

_groq_client: Groq | None = None
_genai_client: "genai.Client | None" = None


@dataclass
class LLMResult:
    content: dict[str, Any] | str
    tokens_used: int
    raw_response: Any


def _lazy_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        from Config.config import CONFIG

        _groq_client = Groq(api_key=CONFIG.models.groq_api_key)
    return _groq_client


def _lazy_genai_client() -> "genai.Client":
    global _genai_client
    if _genai_client is None:
        from Config.config import CONFIG

        api_key = getattr(CONFIG.models, "gemini_api_key", None)
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client


# ── Public API ─────────────────────────────────────────────────

def call_groq(
    system: str,
    user: str,
    model: str,
    schema: type[BaseModel] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    reasoning_effort: str = "low",
) -> LLMResult:
    """
    The only path to a Groq completion in the codebase.

    `schema`: requests Structured Outputs (`response_format` /
    json_schema) built from the Pydantic model, then locally
    re-validates the response against that same model. Raises
    LLMSchemaViolation on mismatch — see module docstring.

    `tools`: passed straight through for tool-calling call sites
    (e.g. orchestration/conversation_agent.py, agents/08 — not yet
    built against this gateway). This function does NOT parse
    `tool_calls` out of the response for you; that shape isn't spec'd
    yet. Ask before assuming it.
    """
    client = _lazy_groq_client()

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "reasoning_effort": reasoning_effort,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if tools is not None:
        kwargs["tools"] = tools
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
            },
        }

    response, tokens_used = _call_with_retry(
        lambda: _do_groq_call(client, kwargs), provider="groq"
    )

    raw_text = response.choices[0].message.content
    content: dict[str, Any] | str = (
        _validate(raw_text, schema, provider="groq") if schema is not None else raw_text
    )

    return LLMResult(content=content, tokens_used=tokens_used, raw_response=response)


def call_gemini(
    system: str,
    user: str,
    model: str,
    schema: type[BaseModel] | None = None,
    temperature: float = 0.0,
) -> LLMResult:
    """The only path to a Gemini completion in the codebase. Same
    validation contract as call_groq — see module docstring."""
    client = _lazy_genai_client()

    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "system_instruction": system,
    }
    if schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = schema

    response, tokens_used = _call_with_retry(
        lambda: _do_gemini_call(client, model, user, config_kwargs), provider="gemini"
    )

    raw_text = response.text
    content: dict[str, Any] | str = (
        _validate(raw_text, schema, provider="gemini") if schema is not None else raw_text
    )

    return LLMResult(content=content, tokens_used=tokens_used, raw_response=response)


# ── Internals ──────────────────────────────────────────────────

def _do_groq_call(client: Groq, kwargs: dict[str, Any]) -> tuple[Any, int]:
    response = client.chat.completions.create(**kwargs)
    usage = getattr(response, "usage", None)
    tokens_used = getattr(usage, "total_tokens", 0) or 0
    return response, tokens_used


def _do_gemini_call(
    client: "genai.Client", model: str, user: str, config_kwargs: dict[str, Any]
) -> tuple[Any, int]:
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=genai_types.GenerateContentConfig(**config_kwargs),
    )
    usage = getattr(response, "usage_metadata", None)
    tokens_used = getattr(usage, "total_token_count", 0) or 0
    return response, tokens_used


def _call_with_retry(fn, provider: str) -> Any:
    """Transient/systemic failures only — never called for schema
    violations, those are raised separately by _validate()."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt == _MAX_RETRIES:
                raise LLMCallFailed(
                    f"{provider} call failed after {attempt + 1} attempt(s): {e}"
                ) from e
            sleep_for = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "[llm.client] %s call failed (attempt %d/%d), retrying in %.1fs: %s",
                provider, attempt + 1, _MAX_RETRIES + 1, sleep_for, e,
            )
            time.sleep(sleep_for)
    raise LLMCallFailed(f"{provider} call failed: {last_exc}") from last_exc


def _is_retryable(exc: Exception) -> bool:
    """
    Deliberately duck-typed rather than importing specific exception
    classes (e.g. groq.RateLimitError, google.genai.errors.APIError):
    I don't have your pinned SDK versions confirmed, and guessing wrong
    class names would be worse than this. Both SDKs raise HTTP-style
    exceptions that carry a status_code (or code) attribute in current
    versions — retry only on 429 and 5xx, since retrying a 4xx bad
    request or auth failure can't succeed on attempt 2.

    Worth tightening to exact exception types once versions are
    pinned — flagging as a known simplification, not a final design.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status is None:
        # No status usually means a connection/timeout-level failure
        # rather than a well-formed API error response — treat as
        # transient rather than assume it's unretryable.
        return True
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status == 429 or 500 <= status < 600


def _validate(raw_text: str | None, schema: type[BaseModel], provider: str) -> dict[str, Any]:
    if not raw_text:
        raise LLMSchemaViolation(
            f"{provider} returned no content to validate against {schema.__name__}",
            raw_response=raw_text,
        )
    try:
        validated = schema.model_validate_json(raw_text)
    except ValidationError as e:
        raise LLMSchemaViolation(
            f"{provider} response failed validation against {schema.__name__}: {e}",
            raw_response=raw_text,
            validation_errors=e.errors(),
        ) from e
    return validated.model_dump()