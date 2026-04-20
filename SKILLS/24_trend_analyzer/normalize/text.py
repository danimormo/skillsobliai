"""Text → ProductFingerprint."""

from __future__ import annotations

import logging

from core.errors import InvalidParamsError

from ..cost_tracker import CostTracker
from ..llm import call_haiku_json
from ..schemas import ProductFingerprint
from ._prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"
MAX_TEXT_LEN = 500


async def normalize_text(raw: str, cost: CostTracker) -> ProductFingerprint:
    text = (raw or "").strip()
    if not text:
        raise InvalidParamsError(
            message="text input is empty",
            skill=SKILL_NAME,
            code="INVALID_PARAMS",
        )
    text = text[:MAX_TEXT_LEN]

    payload = await call_haiku_json(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(payload=f'free text: "{text}"'),
        cost=cost,
        operation="normalize_text",
        max_tokens=400,
    )

    return _to_fingerprint(payload, source_kind="text", raw_input=text)


def _to_fingerprint(data: dict, *, source_kind: str, raw_input: str) -> ProductFingerprint:
    """Coerce a loose LLM payload into the strict ProductFingerprint model."""
    secondary = data.get("secondary_keywords") or []
    if isinstance(secondary, str):
        secondary = [s.strip() for s in secondary.split(",") if s.strip()]

    attrs = data.get("product_attributes") or []
    if isinstance(attrs, str):
        attrs = [s.strip() for s in attrs.split(",") if s.strip()]

    return ProductFingerprint(
        primary_keyword=str(data.get("primary_keyword", "")).strip() or raw_input[:40],
        secondary_keywords=[str(s).strip().lower() for s in secondary][:5],
        category=data.get("category") or "other",
        estimated_retail_price_usd=_coerce_price(data.get("estimated_retail_price_usd")),
        product_attributes=[str(s).strip() for s in attrs][:5],
        source_kind=source_kind,  # type: ignore[arg-type]
        raw_input=raw_input[:500],
    )


def _coerce_price(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
