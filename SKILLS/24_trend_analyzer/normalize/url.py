"""URL → ProductFingerprint.

Fetches the page, extracts title + meta description + first ~1500 chars of
visible text via selectolax, and hands that off to the same LLM prompt used
for plain text normalization.
"""

from __future__ import annotations

import logging
import re

import httpx
from selectolax.parser import HTMLParser

from core.errors import UpstreamError

from ..cost_tracker import CostTracker
from ..llm import call_haiku_json
from ..schemas import ProductFingerprint
from ._prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .text import _to_fingerprint

logger = logging.getLogger(__name__)

SKILL_NAME = "trend-analyzer"
REQUEST_TIMEOUT_S = 10.0
MAX_BODY_BYTES = 500_000
MAX_TEXT_CHARS = 1500

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}


_WHITESPACE = re.compile(r"\s+")


async def normalize_url(url: str, cost: CostTracker) -> ProductFingerprint:
    text_blob = await _fetch_product_page_text(url)

    payload = await call_haiku_json(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_TEMPLATE.format(payload=f"product page scrape:\n{text_blob}"),
        cost=cost,
        operation="normalize_url",
        max_tokens=450,
    )

    return _to_fingerprint(payload, source_kind="url", raw_input=url)


async def _fetch_product_page_text(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise UpstreamError(
            message=f"Failed to fetch URL: {exc}",
            skill=SKILL_NAME,
            code="CONNECTION",
        ) from exc

    if resp.status_code >= 400:
        raise UpstreamError(
            message=f"URL returned HTTP {resp.status_code}",
            skill=SKILL_NAME,
            code="UPSTREAM_ERROR",
        )

    body = resp.content[:MAX_BODY_BYTES]
    return extract_visible_text(body)


def extract_visible_text(html_bytes: bytes | str) -> str:
    """Return title + meta description + up to ``MAX_TEXT_CHARS`` of visible text."""
    parser = HTMLParser(html_bytes)

    parts: list[str] = []

    title_node = parser.css_first("title")
    if title_node and title_node.text():
        parts.append(f"title: {title_node.text().strip()}")

    meta_desc = parser.css_first('meta[name="description"]') or parser.css_first(
        'meta[property="og:description"]'
    )
    if meta_desc:
        desc = meta_desc.attributes.get("content", "")
        if desc:
            parts.append(f"description: {desc.strip()}")

    og_title = parser.css_first('meta[property="og:title"]')
    if og_title:
        og = og_title.attributes.get("content", "")
        if og:
            parts.append(f"og_title: {og.strip()}")

    for node in parser.css("script, style, noscript"):
        node.decompose()

    body_text = parser.body.text(separator=" ") if parser.body else ""
    body_text = _WHITESPACE.sub(" ", body_text).strip()
    if body_text:
        parts.append(f"body: {body_text[:MAX_TEXT_CHARS]}")

    return "\n".join(parts)
