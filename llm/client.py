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


def call_groq(
    system: str,
    user: str,
    model: str,
    schema: type[BaseModel] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    reasoning_effort: str = "low",
) -> LLMResult:
    # FIX: client construction is now wrapped and re-raised as
    # LLMCallFailed. Previously a construction-time failure (bad api key
    # format, SDK-internal validation error, etc.) escaped as whatever
    # raw exception type the SDK produced -- silently breaking this
    # module's own documented contract that callers only need to catch
    # (LLMCallFailed, LLMSchemaViolation). Confirmed by test: a caller
    # using exactly that narrow except clause did not catch a simulated
    # construction failure before this fix, and does after it.
    try:
        client = _lazy_groq_client()
    except Exception as e:
        raise LLMCallFailed(f"groq client construction failed: {e}") from e

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
        _validate(raw_text, schema, provider="groq", tokens_used=tokens_used) if schema is not None else raw_text
    )

    return LLMResult(content=content, tokens_used=tokens_used, raw_response=response)


def call_gemini(
    system: str,
    user: str,
    model: str,
    schema: type[BaseModel] | None = None,
    temperature: float = 0.0,
) -> LLMResult:
    # FIX: see call_groq's matching fix note.
    try:
        client = _lazy_genai_client()
    except Exception as e:
        raise LLMCallFailed(f"gemini client construction failed: {e}") from e

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
        _validate(raw_text, schema, provider="gemini", tokens_used=tokens_used) if schema is not None else raw_text
    )

    return LLMResult(content=content, tokens_used=tokens_used, raw_response=response)


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
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status is None:
        return True
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status == 429 or 500 <= status < 600


def _validate(raw_text: str | None, schema: type[BaseModel], provider: str, tokens_used: int = 0) -> dict[str, Any]:
    """
    FIX: tokens_used is now attached to any LLMSchemaViolation raised
    here via a plain attribute set on the exception instance AFTER
    construction (exc.tokens_used = tokens_used), not via a constructor
    parameter. This is deliberate: llm/errors.py's real source has never
    been provided, so this avoids assuming a constructor signature it
    may not have. Dynamic attribute assignment works on any ordinary
    exception instance regardless of its __init__.

    Before this fix: a schema-violating response still consumed real
    API tokens (the call succeeded; only local validation failed), but
    those tokens were completely unrecoverable -- LLMSchemaViolation
    carried no token information at all, so no caller could account for
    that spend. Confirmed by test. Callers that want to record spend
    even on a failed-validation attempt can now do
    `getattr(exc, "tokens_used", 0)` in their except block. This is
    opt-in for callers -- no existing call site's behavior changes
    unless it's updated to read this new attribute.
    """
    if not raw_text:
        exc = LLMSchemaViolation(
            f"{provider} returned no content to validate against {schema.__name__}",
            raw_response=raw_text,
        )
        exc.tokens_used = tokens_used
        raise exc
    try:
        validated = schema.model_validate_json(raw_text)
    except ValidationError as e:
        exc = LLMSchemaViolation(
            f"{provider} response failed validation against {schema.__name__}: {e}",
            raw_response=raw_text,
            validation_errors=e.errors(),
        )
        exc.tokens_used = tokens_used
        raise exc from e
    return validated.model_dump()