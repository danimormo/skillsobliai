"""Thin async wrapper around Anthropic Claude Haiku 4.5 for this skill.

All normalization and creative-generation calls route through :func:`call_haiku_json`
so cost-tracking, retry, and JSON-parsing live in one place.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from core.config import settings
from core.errors import UpstreamError

from .cost_tracker import CostTracker

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"
DEFAULT_MAX_TOKENS = 600

# Used only when the SDK response omits usage (e.g. in tests).
_FALLBACK_INPUT_TOKENS = 500
_FALLBACK_OUTPUT_TOKENS = 200


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json(raw: str) -> Any:
    """Tolerant JSON extraction — strips code fences / prose around the object."""
    raw = raw.strip()
    if not raw:
        raise ValueError("empty LLM response")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = _JSON_FENCE.search(raw)
    if m:
        return json.loads(m.group(1))

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw[start : end + 1])

    raise ValueError(f"no JSON object found in LLM response: {raw[:200]!r}")


async def call_haiku_json(
    *,
    system: str,
    user: str,
    cost: CostTracker,
    operation: str,
    image_b64: str | None = None,
    image_media_type: str = "image/jpeg",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Call Claude Haiku 4.5 and return a parsed JSON dict.

    :param system:       system prompt
    :param user:         user prompt (text portion)
    :param cost:         request-scoped cost tracker; usage is recorded automatically
    :param operation:    short label for cost-entry provenance
    :param image_b64:    optional base64-encoded image for vision input
    :param image_media_type: MIME type when ``image_b64`` is provided
    :param max_tokens:   output cap

    :raises UpstreamError: on auth / API / parse failures
    """
    if not settings.ANTHROPIC_API_KEY:
        raise UpstreamError(
            message="ANTHROPIC_API_KEY is not configured.",
            skill=SKILL_NAME,
            code="MISSING_API_KEY",
        )

    content: list[dict[str, Any]] = []
    if image_b64:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type,
                    "data": image_b64,
                },
            }
        )
    content.append({"type": "text", "text": user})

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL_FAST,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError as exc:
        raise UpstreamError(
            message=f"Invalid Anthropic API key: {exc}",
            skill=SKILL_NAME,
            code="INVALID_API_KEY",
        ) from exc
    except anthropic.APIError as exc:
        raise UpstreamError(
            message=f"Anthropic API error: {exc}",
            skill=SKILL_NAME,
            code="UPSTREAM_ERROR",
        ) from exc

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", _FALLBACK_INPUT_TOKENS)
    output_tokens = getattr(usage, "output_tokens", _FALLBACK_OUTPUT_TOKENS)
    cost.add_claude_haiku(
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    try:
        text = response.content[0].text
    except (IndexError, AttributeError) as exc:
        raise UpstreamError(
            message="Claude returned an empty response.",
            skill=SKILL_NAME,
            code="EMPTY_RESPONSE",
        ) from exc

    try:
        return _extract_json(text)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("llm.parse_failed op=%s raw=%r", operation, text[:200])
        raise UpstreamError(
            message=f"Failed to parse Claude JSON response: {exc}",
            skill=SKILL_NAME,
            code="PARSE_ERROR",
        ) from exc
