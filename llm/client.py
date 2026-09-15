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
_BACKOFF_BASE_SECONDS = 2.0

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
        _genai_client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=60000),
        )
    return _genai_client


def _salvage_groq_failed_generation(exc: Exception) -> str | None:
    import re
    # Groq returns error response dict with body
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        # Could be an attribute on response
        resp = getattr(exc, "response", None)
        if resp and hasattr(resp, "json"):
            try:
                body = resp.json()
            except Exception:
                body = None
    if isinstance(body, dict):
        err = body.get("error", {})
        if isinstance(err, dict):
            failed = err.get("failed_generation")
            if failed and isinstance(failed, str):
                cleaned = re.sub(r'\*\*\s*("[^"]+")\s*\*\*', r'\1', failed)
                cleaned = re.sub(r'\*\*\s*("[^"]+")', r'\1', cleaned)
                return cleaned.strip()
    return None


def call_groq(
    system: str,
    user: str,
    model: str,
    schema: type[BaseModel] | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    reasoning_effort: str = "low",
    max_tokens: int | None = None,
) -> LLMResult:
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
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
            },
        }

    try:
        response, tokens_used = _call_with_retry(
            lambda: _do_groq_call(client, kwargs), provider="groq"
        )
        raw_text = response.choices[0].message.content
    except Exception as e:
        # 1. Attempt to salvage any near-complete JSON from Groq's failed_generation
        salvaged = _salvage_groq_failed_generation(e)
        if salvaged and schema is not None:
            try:
                content = _validate(salvaged, schema, provider="groq-salvaged")
                logger.info("[llm.client] Successfully salvaged Groq failed_generation payload.")
                return LLMResult(content=content, tokens_used=0, raw_response=salvaged)
            except Exception:
                pass

        # 2. If json_schema mode failed, retry once with json_object mode (less strict grammar)
        if schema is not None and "response_format" in kwargs:
            logger.warning("[llm.client] Groq json_schema call failed (%s); retrying with response_format={'type': 'json_object'}...", e)
            kwargs_fallback = dict(kwargs)
            kwargs_fallback["response_format"] = {"type": "json_object"}
            try:
                response, tokens_used = _call_with_retry(
                    lambda: _do_groq_call(client, kwargs_fallback), provider="groq"
                )
                raw_text = response.choices[0].message.content
                content = _validate(raw_text, schema, provider="groq-json-object", tokens_used=tokens_used)
                return LLMResult(content=content, tokens_used=tokens_used, raw_response=response)
            except Exception:
                pass
        raise

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

    try:
        response, tokens_used = _call_with_retry(
            lambda: _do_gemini_call(client, model, user, config_kwargs), provider="gemini"
        )
    except LLMCallFailed as e:
        # If the requested model failed (e.g. temporary 503/504) and was not gemini-3.6-flash, try gemini-3.6-flash as backup
        if model != "gemini-3.6-flash":
            logger.warning("[llm.client] Gemini %s failed (%s); trying fallback model gemini-3.6-flash...", model, e)
            try:
                response, tokens_used = _call_with_retry(
                    lambda: _do_gemini_call(client, "gemini-3.6-flash", user, config_kwargs), provider="gemini"
                )
            except Exception:
                raise e
        else:
            raise

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

    import re
    cleaned = raw_text.strip()
    # Strip markdown code blocks e.g. ```json ... ```
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    # Strip accidental bold markers on JSON keys e.g. **"hook"**:
    cleaned = re.sub(r'\*\*\s*("[^"]+")\s*\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*\*\s*("[^"]+")', r'\1', cleaned)

    try:
        validated = schema.model_validate_json(cleaned)
    except ValidationError as e:
        exc = LLMSchemaViolation(
            f"{provider} response failed validation against {schema.__name__}: {e}",
            raw_response=raw_text,
            validation_errors=e.errors(),
        )
        exc.tokens_used = tokens_used
        raise exc from e
    return validated.model_dump()