"""Google Shopping retail-price probe.

Scrapes ``google.com/search?tbm=shop&q=…`` with the shared Playwright
helper. Returns median + (min, max) of the retail prices shown on the
first results page.
"""

from __future__ import annotations

import hashlib
import logging
import re
import statistics
from typing import Iterable

from selectolax.parser import HTMLParser

from .. import cache
from ..cost_tracker import CostTracker
from . import _browser

logger = logging.getLogger(__name__)

PROVIDER = "google_shopping"

SEARCH_URL = "https://www.google.com/search?tbm=shop&hl=en&gl=us&q={q}"


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    no_cache: bool = False,
) -> tuple[float | None, tuple[float, float] | None]:
    key = _cache_key(primary_keyword)

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if isinstance(hit, dict):
            median = hit.get("median")
            rng = hit.get("range")
            rng_tuple = tuple(rng) if isinstance(rng, (list, tuple)) and len(rng) == 2 else None
            return (float(median) if median is not None else None, rng_tuple)  # type: ignore[return-value]

    try:
        html = await _browser.fetch_html(
            SEARCH_URL.format(q=_encode(primary_keyword)),
            wait_selector='div[data-docid], div[role="heading"]',
            cookie_namespace=PROVIDER,
        )
    except Exception as exc:
        logger.warning("google_shopping.fetch_failed kw=%r err=%s", primary_keyword, exc)
        return await _stale_or_none(key)

    median, price_range = parse_prices(html)
    cost.add(provider=PROVIDER, operation="scrape", usd=0.0, note=primary_keyword)

    if not no_cache and median is not None:
        await cache.set(
            PROVIDER, key,
            {"median": median, "range": list(price_range) if price_range else None},
        )
    return median, price_range


async def _stale_or_none(key: str) -> tuple[float | None, tuple[float, float] | None]:
    stale = await cache.get_stale(PROVIDER, key)
    if isinstance(stale, dict):
        rng = stale.get("range")
        rng_tuple = tuple(rng) if isinstance(rng, (list, tuple)) and len(rng) == 2 else None
        return (
            float(stale["median"]) if stale.get("median") is not None else None,
            rng_tuple,  # type: ignore[return-value]
        )
    return None, None


# ── Parser ─────────────────────────────────────────────────────────────────


_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")


def parse_prices(
    html: str,
) -> tuple[float | None, tuple[float, float] | None]:
    parser = HTMLParser(html)
    text = parser.body.text(separator=" ") if parser.body else ""

    prices: list[float] = []
    for m in _PRICE_RE.finditer(text):
        val = _to_float(m.group(1))
        if val is not None and 1 < val < 10_000:
            prices.append(val)

    if not prices:
        return None, None

    prices = prices[:25]
    median = round(statistics.median(prices), 2)
    return median, (min(prices), max(prices))


def _to_float(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _encode(s: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(s)


def _cache_key(keyword: str) -> str:
    return hashlib.sha1(keyword.strip().lower().encode()).hexdigest()
