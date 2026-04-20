"""TikTok Creative Center provider.

TikTok's Creative Center (https://ads.tiktok.com/business/creativecenter/…)
exposes several public JSON endpoints that power the popular-hashtag and
trending-product pages. We hit the search-hashtag API with a plain ``httpx``
request (no JS needed) and fall back gracefully when TikTok reshuffles
the URL shape (they do, roughly every 6 months).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from .. import cache
from ..cost_tracker import CostTracker
from ..schemas import TikTokSignal

logger = logging.getLogger(__name__)

PROVIDER = "tiktok"

# Discoverable via browser devtools; structure kept loose to tolerate changes.
CC_SEARCH_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
    "?period=30&page=1&limit=20&country_code=US&keyword={kw}"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en",
}
TIMEOUT_S = 10.0


async def fetch(
    primary_keyword: str,
    cost: CostTracker,
    *,
    no_cache: bool = False,
) -> TikTokSignal:
    key = _cache_key(primary_keyword)

    if not no_cache:
        hit = await cache.get(PROVIDER, key)
        if hit is not None:
            return TikTokSignal.model_validate(hit)

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT_S) as client:
            resp = await client.get(
                CC_SEARCH_URL.format(kw=_encode(primary_keyword))
            )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning("tiktok.connect_failed kw=%r err=%s", primary_keyword, exc)
        return _fallback_or_empty(key)

    if resp.status_code >= 400:
        logger.warning("tiktok.http_error kw=%r status=%s", primary_keyword, resp.status_code)
        stale = await cache.get_stale(PROVIDER, key)
        if stale is not None:
            return TikTokSignal.model_validate(stale)
        return TikTokSignal()

    signal = parse_response(resp.json(), primary_keyword)
    cost.add(provider=PROVIDER, operation="fetch", usd=0.0, note=primary_keyword)

    if not no_cache:
        await cache.set(PROVIDER, key, signal.model_dump(mode="json"))
    return signal


async def _fallback_or_empty(key: str) -> TikTokSignal:
    stale = await cache.get_stale(PROVIDER, key)
    if stale is not None:
        return TikTokSignal.model_validate(stale)
    return TikTokSignal()


# ── Parser ─────────────────────────────────────────────────────────────────


def parse_response(payload: Any, keyword: str) -> TikTokSignal:
    """Robust against TikTok moving keys around between releases."""
    hashtags = _dig(payload, "data", "list") or _dig(payload, "list") or []
    if not isinstance(hashtags, list):
        return TikTokSignal()

    matching = []
    kw_low = keyword.lower().replace(" ", "")
    for item in hashtags:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("hashtag_name") or item.get("name") or "").lower()
        if kw_low in tag.replace(" ", ""):
            matching.append(item)

    mentions = len(matching) or len(hashtags)
    # Rank value — prefer ``rank_diff`` (growth), else ``rank`` inverted to
    # a 0-100 score so "rank 1" becomes 100.
    scores: list[float] = []
    views: list[int] = []
    for item in matching or hashtags:
        rank_diff = item.get("rank_diff")
        rank = item.get("rank")
        if isinstance(rank_diff, (int, float)):
            scores.append(float(rank_diff))
        elif isinstance(rank, (int, float)):
            scores.append(max(0.0, 100.0 - float(rank)))

        for key_name in ("publish_cnt", "view", "view_count", "video_views"):
            v = item.get(key_name)
            if isinstance(v, (int, float)):
                views.append(int(v))
                break

    hashtag_score = round(sum(scores) / len(scores), 2) if scores else None

    return TikTokSignal(
        hashtag_score=hashtag_score,
        top_videos_views=views[:10],
        product_mentions=mentions,
    )


def _dig(obj: Any, *keys: str) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _encode(s: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(s)


def _cache_key(keyword: str) -> str:
    return hashlib.sha1(keyword.strip().lower().encode()).hexdigest()
