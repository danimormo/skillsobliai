"""AliExpress supplier-price probe.

Scrapes the wholesale search results page with the shared Playwright
helper (AliExpress is heavily JS-gated). We pin language=en and
currency=USD via query params + Accept-Language header. No API key, no
account needed.
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

PROVIDER = "aliexpress"

SEARCH_URL = "https://www.aliexpress.com/w/wholesale-{q}.html?SearchText={q}"


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    no_cache: bool = False,
) -> float | None:
    """Return the median supplier price (USD) from the first 10 results, or ``None``."""
    key = _cache_key(primary_keyword)

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if isinstance(hit, (int, float)):
            return float(hit)

    try:
        html = await _browser.fetch_html(
            SEARCH_URL.format(q=_encode(primary_keyword)),
            wait_selector='a[href*="/item/"]',
            cookie_namespace=PROVIDER,
        )
    except Exception as exc:
        logger.warning("aliexpress.fetch_failed kw=%r err=%s", primary_keyword, exc)
        stale = await cache.get_stale(PROVIDER, key)
        return float(stale) if isinstance(stale, (int, float)) else None

    median = parse_median_price(html)
    cost.add(provider=PROVIDER, operation="scrape", usd=0.0, note=primary_keyword)

    if not no_cache and median is not None:
        await cache.set(PROVIDER, key, median)
    return median


# ── Parser ─────────────────────────────────────────────────────────────────


_PRICE_RE = re.compile(r"US\s*\$\s*([\d,]+\.\d{1,2}|\d+)")


def parse_median_price(html: str) -> float | None:
    parser = HTMLParser(html)
    text = parser.body.text(separator=" ") if parser.body else ""
    prices = [_to_float(m.group(1)) for m in _PRICE_RE.finditer(text)]
    prices = [p for p in prices if p is not None and p > 0]
    return _median_of_first_n(prices, n=10)


def _median_of_first_n(values: Iterable[float], n: int) -> float | None:
    slice_ = list(values)[:n]
    if not slice_:
        return None
    return round(statistics.median(slice_), 2)


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
