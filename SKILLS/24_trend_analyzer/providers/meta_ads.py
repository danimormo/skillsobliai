"""Meta Ads Library provider — scrapes the public UI (no Graph API).

The Graph API /ads_archive endpoint is gated to political/EU ads and
requires verified business identity. The public UI at
``facebook.com/ads/library/?q=…`` is crawlable without login, so we
scrape that instead.

Rate limiting: max 1 call / 30s / host (enforced by the module-level
``_LAST_CALL`` guard), random 5-15s delay inside :func:`_browser.fetch_html`.

Extracted signal
----------------
- active_ads_7d / active_ads_30d
- top_advertisers: list[page_id / page_name]
- earliest_ad_date: how "fresh" the product is
- media_distribution: {image, video, carousel}
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import date, datetime, timedelta

from selectolax.parser import HTMLParser

from .. import cache
from ..cost_tracker import CostTracker
from ..schemas import MetaAdsSignal
from . import _browser

logger = logging.getLogger(__name__)

PROVIDER = "meta_ads"

MIN_SECONDS_BETWEEN_CALLS = 30.0
BASE_URL = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={q}"
WAIT_SELECTOR = '[role="main"]'

_LAST_CALL_AT: float = 0.0
_LOCK = asyncio.Lock()


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    no_cache: bool = False,
) -> MetaAdsSignal:
    key = _cache_key(primary_keyword)

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if hit is not None:
            return MetaAdsSignal.model_validate(hit)

    async with _LOCK:
        await _respect_rate_limit()
        try:
            html = await _browser.fetch_html(
                BASE_URL.format(q=_url_encode(primary_keyword)),
                wait_selector=WAIT_SELECTOR,
                cookie_namespace=PROVIDER,
            )
        except Exception as exc:
            logger.warning("meta_ads.fetch_failed kw=%r err=%s", primary_keyword, exc)
            stale = await cache.get_stale(PROVIDER, key)
            if stale is not None:
                return MetaAdsSignal.model_validate(stale)
            return MetaAdsSignal()
        finally:
            _mark_call()

    signal = parse_library_html(html)
    cost.add(provider=PROVIDER, operation="scrape", usd=0.0, note=primary_keyword)

    if not no_cache:
        await cache.set(PROVIDER, key, signal.model_dump(mode="json"))
    return signal


# ── Rate-limit bookkeeping ─────────────────────────────────────────────────


async def _respect_rate_limit() -> None:
    global _LAST_CALL_AT
    elapsed = time.monotonic() - _LAST_CALL_AT
    wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
    if wait > 0 and _LAST_CALL_AT > 0:
        logger.debug("meta_ads.rate_limit sleeping=%.1fs", wait)
        await asyncio.sleep(wait)


def _mark_call() -> None:
    global _LAST_CALL_AT
    _LAST_CALL_AT = time.monotonic()


# ── Parsing ────────────────────────────────────────────────────────────────


_ACTIVE_COUNT_RE = re.compile(
    r"(?:~?\s*)(\d[\d,\.]*)\s*(?:results|ads|annunci)", re.IGNORECASE
)
_DATE_RE = re.compile(
    r"(?:Started running on|Started|Running since)\s+([A-Z][a-z]{2,8})\s+(\d{1,2}),\s*(\d{4})"
)


def parse_library_html(html: str) -> MetaAdsSignal:
    """Best-effort parser tolerant of Meta's frequently-changing DOM."""
    parser = HTMLParser(html)

    text = parser.body.text(separator=" ") if parser.body else ""
    active_count = _extract_active_count(text)

    start_dates = _extract_start_dates(text)
    earliest = min(start_dates) if start_dates else None
    now = date.today()

    ads_7d = sum(1 for d in start_dates if (now - d).days <= 7)
    ads_30d = sum(1 for d in start_dates if (now - d).days <= 30) or active_count

    advertisers = _extract_advertisers(parser)
    media_dist = _extract_media_distribution(parser)

    return MetaAdsSignal(
        active_ads_7d=ads_7d,
        active_ads_30d=ads_30d,
        top_advertisers=advertisers[:10],
        earliest_ad_date=earliest,
        media_distribution=media_dist,
    )


def _extract_active_count(text: str) -> int:
    m = _ACTIVE_COUNT_RE.search(text)
    if not m:
        return 0
    try:
        return int(m.group(1).replace(",", "").replace(".", ""))
    except ValueError:
        return 0


def _extract_start_dates(text: str) -> list[date]:
    dates: list[date] = []
    for m in _DATE_RE.finditer(text):
        month_name, day, year = m.group(1), m.group(2), m.group(3)
        try:
            parsed = datetime.strptime(
                f"{month_name[:3]} {day} {year}", "%b %d %Y"
            ).date()
        except ValueError:
            continue
        if parsed <= date.today() + timedelta(days=1):
            dates.append(parsed)
    return dates


def _extract_advertisers(parser: HTMLParser) -> list[str]:
    # Meta renders advertiser names as ``<a role="link">Name</a>`` inside the
    # ad card. We collect unique anchor labels that look like page names.
    seen: list[str] = []
    for a in parser.css('a[role="link"]'):
        txt = (a.text() or "").strip()
        if not txt or len(txt) > 80:
            continue
        if txt.lower() in {"see ad details", "see summary", "library id"}:
            continue
        if txt not in seen:
            seen.append(txt)
    return seen


def _extract_media_distribution(parser: HTMLParser) -> dict[str, int]:
    images = len(parser.css("img"))
    videos = len(parser.css("video"))
    carousels = len(parser.css('[aria-label*="carousel" i], [role="listbox"]'))
    return {"image": images, "video": videos, "carousel": carousels}


# ── Helpers ────────────────────────────────────────────────────────────────


def _url_encode(s: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(s)


def _cache_key(keyword: str) -> str:
    return hashlib.sha1(keyword.strip().lower().encode()).hexdigest()
